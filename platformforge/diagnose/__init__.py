"""Compose graph + findings into a per-node diagnosis (§7 `diagnose`).

Answers "o que há de errado com X?" with evidence: the node's facts, the
findings touching it (by evidence location/source), its blast radius, and
what remains unresolved. Never infers — absent facts stay `unresolved`.
"""

from __future__ import annotations

from typing import Any

from platformforge.graph.model import Graph
from platformforge.graph.model import node_id as mk_node_id
from platformforge.graph.query import blast_radius, dependencies, dependents


def _fact_nodes(fact: dict) -> set[str]:
    """Node ids a fact contributes to, via its graph contribution."""
    out = {fact.get("attrs", {}).get("node_id") or
           fact.get("attrs", {}).get("id")}
    for n in ((fact.get("attrs") or {}).get("graph") or {}).get("nodes", []):
        out.add(mk_node_id(n["kind"], n["label"]))
    return {x for x in out if x}


def _findings_for(findings: list[dict], node_id: str,
                  facts_by_id: dict[str, dict]) -> list[dict]:
    out = []
    for f in findings:
        for e in f.get("evidence", []):
            fact = facts_by_id.get(e, {})
            loc = str(fact.get("location") or fact.get("source") or "")
            if node_id in _fact_nodes(fact) or node_id in loc \
                    or e == node_id:
                out.append({"rule_id": f.get("rule_id"),
                            "severity": f.get("severity"),
                            "title": f.get("title"),
                            "via": e})
                break
    return out


def diagnose(g: Graph, node_id: str, findings: list[dict],
             facts: list[dict] | None = None,
             criticality: dict | None = None) -> dict[str, Any]:
    node = g.nodes.get(node_id)
    if node is None:
        return {"refusal": "platform.diagnose.unknown_node",
                "node": node_id,
                "unlock": "platformforge graph stats → pick a node id"}
    facts_by_id = {f.get("fact_id"): f for f in facts or []}
    node_facts = [f for f in facts_by_id.values()
                  if node_id in _fact_nodes(f)
                  or node_id in str(f.get("source", ""))]
    blast = blast_radius(g, node_id)
    deps = sorted(dependencies(g, node_id))
    deps_of = sorted(dependents(g, node_id))

    unresolved = []
    for want in ("owner", "criticality", "env"):
        if want not in node.attrs:
            unresolved.append(f"node.attrs.{want}")
    if node_facts == []:
        unresolved.append("node_facts (no analyzer emitted facts for node)")

    from platformforge.risk.engine import assess_change
    from platformforge.risk.engine import criticality as crit
    sig = {"blast_radius": len(blast.get("nodes", [])),
           "declared_criticality": crit(node.attrs)}
    sev = assess_change(sig)
    return {"node": node_id, "kind": node.kind, "attrs": node.attrs,
            "facts": node_facts,
            "findings": _findings_for(findings, node_id, facts_by_id),
            "dependencies": deps, "dependents": deps_of,
            "blast_radius": blast, "risk": sev, "unresolved": unresolved}
