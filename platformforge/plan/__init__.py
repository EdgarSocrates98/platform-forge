"""Remediation planner (§7 `plan`, §156–157) — findings → change DAG.

Ordering is not severity-only. Each step is scored on:

    severity → blast radius → reversibility → prerequisites

and wired into a DAG (`edges`/`depends_on`) when steps interact — e.g. a
request/limits fix is a prerequisite of an HPA fix on the same workload.
A step with no evidence is refused rather than planned.
"""

from __future__ import annotations

from typing import Any

_SEV = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}

# §157 — prerequisite edges between rule families. A rule id prefix in
# `key` must land before any rule whose id is in `needs`.
_PREREQS: dict[str, tuple[str, ...]] = {
    "PF-K8S-003": ("PF-K8S-020",),          # requests before HPA targets
    "PF-K8S-004": ("PF-K8S-020",),
    "PF-SEC-020": ("PF-SEC-040",),          # fix image provenance first
    "PF-IAM-001": ("PF-IAM-002",),          # kill wildcards before chains
}

# rules whose fix is intrinsically reversible (config-only, declarative)
_REVERSIBLE_PREFIX = ("PF-K8S-", "PF-GITOPS-", "PF-FIN-", "PF-CICD-",
                      "PF-SLO-")


def remediation_plan(findings: list[dict],
                     graph: Any | None = None,
                     facts: list[dict] | None = None) -> dict[str, Any]:
    violated = [f for f in findings if f.get("status") == "violated"]
    refused = [f.get("rule_id") for f in findings
               if f.get("status") == "violated" and not f.get("evidence")]

    facts_by_id = {f.get("fact_id"): f for f in facts or []}
    steps = []
    for f in violated:
        if not f.get("evidence"):
            continue
        blast_n = None
        node = None
        if graph is not None:
            from platformforge.graph.query import blast_radius
            for e in f["evidence"]:
                nid = facts_by_id.get(e, {}).get("attrs", {}).get("node_id")
                if nid and nid in graph.nodes:
                    node = nid
                    blast_n = max(blast_n or 0,
                                  len(blast_radius(graph, nid)["nodes"]))
        steps.append({"id": f"step-{len(steps):03d}",
                      "rule_id": f["rule_id"], "title": f.get("title"),
                      "severity": f.get("severity", "medium"),
                      "evidence": f["evidence"], "node": node,
                      "remediation": f.get("remediation", ""),
                      "blast_size": blast_n,
                      "reversible": f["rule_id"].startswith(
                          _REVERSIBLE_PREFIX),
                      "depends_on": [],                      # §157
                      "rollback": "revert the change that violates "
                                  f"{f['rule_id']}; verify with judge"})

    # §156 scoring: severity → blast → irreversible last
    steps.sort(key=lambda s: (_SEV.get(s["severity"], 9),
                              -(s["blast_size"] or 0),
                              not s["reversible"]))

    # §157 — DAG edges: prerequisite rules (any step pair sharing the
    # rule ids — a rule may fire on several facts)
    by_rule: dict[str, list[str]] = {}
    for s in steps:
        by_rule.setdefault(s["rule_id"], []).append(s["id"])
    edges = []
    for prereq, needs in _PREREQS.items():
        for need in needs:
            for pre_id in by_rule.get(prereq, []):
                for dep_id in by_rule.get(need, []):
                    edges.append({"from": pre_id, "to": dep_id,
                                  "why": f"{need} assumes {prereq} "
                                         "is fixed"})
                    for s in steps:
                        if s["id"] == dep_id:
                            s["depends_on"].append(pre_id)
    # same-node steps are sequenced: later steps depend on the first fix
    by_node: dict[str, list[dict]] = {}
    for s in steps:
        if s["node"]:
            by_node.setdefault(s["node"], []).append(s)
    for node, ns in by_node.items():
        if len(ns) > 1:
            first = ns[0]["id"]
            for s in ns[1:]:
                if first not in s["depends_on"]:
                    s["depends_on"].append(first)
                    edges.append({"from": first, "to": s["id"],
                                  "why": f"same node {node}"})
    return {"plan": "platformforge.remediation/v2",
            "dag": {"steps": [s["id"] for s in steps], "edges": edges},
            "steps": steps,
            "counts": {"steps": len(steps), "refused": len(refused),
                       "dag_edges": len(edges)},
            "refused": refused,
            "boundary": "plan is a proposal — apply lives host-side "
                        "(platform.change.core_read_only)"}
