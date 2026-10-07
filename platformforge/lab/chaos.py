"""Chaos lab (§93) — deterministic fault injection *on the graph*.

Offline by construction: a fault removes or degrades nodes in a built
graph, then blast_radius computes the impacted set. Results are declared
simulations (`environment: simulation`), never live fault injection.

Production targets are refused unless the caller passes allow_prod — the
boundary is explicit, not implicit.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from platformforge.graph.model import Graph
from platformforge.graph.query import blast_radius

FAULTS = ("pod_kill", "latency_injection", "dependency_unavailable",
          "dns_failure", "network_loss", "node_unavailable")

# faults that degrade edges (dependencies stay, SLO risk rises)
_DEGRADE = {"latency_injection", "network_loss"}


def chaos(g: Graph, fault: str, target: str,
          allow_prod: bool = False) -> dict[str, Any]:
    if fault not in FAULTS:
        return {"refusal": "platform.chaos.unknown_fault",
                "known": list(FAULTS)}
    node = g.nodes.get(target)
    if node is None:
        return {"refusal": "platform.chaos.unknown_node", "node": target}
    if node.attrs.get("env") == "production" and not allow_prod:
        return {"refusal": "platform.chaos.production_default",
                "node": target,
                "unlock": "re-run with allow_prod=True in a controlled env"}

    blast = blast_radius(g, target)
    degraded = sorted(blast["nodes"])
    impact = {"fault": fault, "target": target,
              "environment": "simulation",
              "mode": ("degraded" if fault in _DEGRADE else "removed"),
              "impacted_total": blast["impacted_total"],
              "impacted_by_class": blast["by_class"],
              "degraded_nodes": degraded,
              "unresolved": [
                  ("post-fault recovery behavior is not observable from "
                   "static artifacts")]}
    return {"chaos": "platformforge.chaos/v1", **impact}


def run_scenario(path: str | Path,
                 allow_prod: bool = False) -> dict[str, Any]:
    """chaos.yaml: {fault, target, facts} → simulation against fixture graph."""
    d = Path(path)
    spec = yaml.safe_load((d / "chaos.yaml").read_text())
    facts_doc = yaml.safe_load((d / spec.get("facts", "facts.json"))
                               .read_text())
    from platformforge.graph import GraphBuilder
    g = GraphBuilder().from_facts(
        facts_doc.get("facts", facts_doc if isinstance(facts_doc, list)
                      else [])).graph
    out = chaos(g, spec["fault"], spec["target"], allow_prod=allow_prod)
    expected = spec.get("expected_impacted")
    if expected is not None and "degraded_nodes" in out:
        out["expected_match"] = \
            sorted(expected) == out["degraded_nodes"]
    return out
