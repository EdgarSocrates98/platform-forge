"""Graph costing — join platform graph (billed_to edges) with cost facts to
price workloads and dependency paths. Missing edges → unresolved, never zero."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from platformforge.graph.model import Graph
from platformforge.graph.query import dependencies


def graph_cost(graph: Graph, cost_facts: list[dict[str, Any]]) -> dict[str, Any]:
    """cost per cost_center via billed_to edges; direct cost per node."""
    node_cost: dict[str, float] = {}
    for f in cost_facts:
        if f.get("kind") != "finops.cost":
            continue
        res = f["attrs"]["resource"]
        node_cost[res] = node_cost.get(res, 0.0) + f["attrs"]["amount"]
    billed: dict[str, str] = {}
    for e in graph.edges.values():
        if e.kind == "billed_to":
            billed[e.src] = e.dst
    per_center: dict[str, float] = defaultdict(float)
    unattributed: list[str] = []
    for nid, amt in node_cost.items():
        # resolve resource node id variants
        cand = [nid] + [n for n in graph.nodes if n.endswith("/" + nid)]
        hit = next((c for c in cand if c in billed), None)
        if hit:
            per_center[billed[hit]] += amt
        else:
            unattributed.append(nid)
    # downstream dependency cost: for each node, sum costs of its deps
    dep_cost = {}
    for nid in graph.nodes:
        deps = dependencies(graph, nid)
        tot = sum(node_cost.get(d.split("/", 1)[-1], 0.0) +
                  node_cost.get(d, 0.0) for d in deps)
        own = node_cost.get(nid, 0.0) or \
            node_cost.get(nid.split("/", 1)[-1], 0.0)
        if own or tot:
            dep_cost[nid] = {"own": round(own, 4),
                             "dependencies": round(tot, 4),
                             "total": round(own + tot, 4)}
    return {"per_cost_center": {k: round(v, 4)
                                for k, v in sorted(per_center.items())},
            "unattributed_resources": sorted(unattributed),
            "dependency_costs": dep_cost,
            "unresolved": bool(unattributed)}
