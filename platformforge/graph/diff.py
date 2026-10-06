"""Graph diff: before/after comparison feeding the change-risk engine."""

from __future__ import annotations

from typing import Any

from platformforge.graph.model import Graph
from platformforge.graph.query import blast_radius, gaps


def diff(before: Graph, after: Graph) -> dict[str, Any]:
    bn, an = set(before.nodes), set(after.nodes)
    be, ae = set(before.edges), set(after.edges)
    changed_nodes = sorted(
        n for n in bn & an
        if before.nodes[n].to_dict() != after.nodes[n].to_dict())
    g_before, g_after = gaps(before), gaps(after)
    flags: dict[str, Any] = {}
    for key in ("external_exposure", "ownership_gaps", "unmonitored",
                "unprotected", "unallocated_cost"):
        flags[key + "_changed"] = g_before[key] != g_after[key]
        flags[key + "_delta"] = {
            "added": sorted(set(g_after[key]) - set(g_before[key])),
            "removed": sorted(set(g_before[key]) - set(g_after[key])),
        }
    # blast-radius deltas for nodes present in both graphs
    br_delta = {}
    for n in sorted(bn & an):
        b = blast_radius(before, n)["impacted_total"]
        a = blast_radius(after, n)["impacted_total"]
        if b != a:
            br_delta[n] = {"before": b, "after": a}
    return {
        "nodes_added": sorted(an - bn), "nodes_removed": sorted(bn - an),
        "nodes_changed": changed_nodes,
        "edges_added": sorted(ae - be), "edges_removed": sorted(be - ae),
        "security_changed": flags["external_exposure_changed"]
            or flags["unprotected_changed"],
        "ownership_changed": flags["ownership_gaps_changed"],
        "cost_changed": flags["unallocated_cost_changed"],
        "observability_changed": flags["unmonitored_changed"],
        "gap_deltas": flags,
        "blast_radius_delta": br_delta,
        "hash_before": before.graph_hash, "hash_after": after.graph_hash,
    }
