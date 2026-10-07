"""Graph diff: before/after comparison feeding the change-risk engine."""

from __future__ import annotations

from typing import Any

from platformforge.graph.model import Graph
from platformforge.graph.query import blast_radius, gaps

# §7 — semantic diff categories. Attr keys / node kinds / edge kinds are
# mapped to a change class; every reported diff cites the backing fact_ids.
_ATTR_CATEGORIES = {
    "identity": ("principal", "role", "policy", "service_account",
                 "identity", "assume", "permissions"),
    "network": ("cidr", "port", "protocol", "subnet", "vpc", "route",
                "gateway", "dns", "peer"),
    "exposure": ("public", "expose", "ingress", "external", "tls",
                 "listener", "anonymous"),
    "ha": ("replicas", "replica", "pdb", "zone", "az", "min_available",
           "multi_az", "standby"),
    "cost": ("cost", "price", "billing", "sku", "instance_type"),
    "slo": ("slo", "sli", "burn", "budget", "availability_target"),
    "runtime": ("image", "runtime", "version", "tag", "digest",
                "command", "args", "env"),
    "region": ("region", "location"),
    "storage": ("volume", "bucket", "storage", "size_gb", "disk",
                "filesystem", "mount"),
    "supply_chain": ("sbom", "signature", "attestation", "provenance",
                     "license", "cve"),
}
_NODE_KIND_CATEGORIES = {
    "identity": {"iam_principal", "role", "policy", "service_account",
                 "workload_identity"},
    "network": {"subnet", "vpc_vnet", "route", "gateway", "nat", "dns"},
    "exposure": {"load_balancer", "ingress", "gateway"},
    "slo": {"slo", "monitor", "alert"},
    "storage": {"volume", "bucket", "database", "cache"},
    "supply_chain": {"sbom", "container_image", "artifact"},
    "deployment": {"workload", "pod", "argocd_application",
                   "fluxcd_resource", "pipeline", "workflow"},
    "region": {"region", "zone"},
}
_EDGE_KIND_CATEGORIES = {
    "identity": {"assumes", "impersonates", "can_access", "uses_secret"},
    "replication": {"replicated_to", "fails_over_to"},
    "deployment": {"deploys_to", "runs_on"},
    "cost": {"billed_to"},
    "security": {"secured_by", "exposes"},
    "network": {"routes_to"},
    "runtime": {"calls", "publishes_to", "consumes", "reads", "writes"},
    "slo": {"observed_by", "alerted_by"},
    "ownership": {"owns"},
    "supply_chain": {"generated_by", "provisioned_by"},
    "ha": {"replicated_to", "fails_over_to", "contained_by"},
}
SEMANTIC_CATEGORIES = ("identity", "network", "exposure", "ownership", "ha",
                       "cost", "security", "slo", "runtime", "region",
                       "storage", "replication", "deployment",
                       "supply_chain")


def _node_fact_ids(node: Any) -> list[str]:
    return sorted(getattr(node, "source_fact_ids", ()) or ())


def _semantic_diff(before: Graph, after: Graph,
                   changed_nodes: list[str]) -> dict[str, Any]:
    out: dict[str, dict[str, Any]] = {
        c: {"changed": False, "nodes": set(), "fact_ids": set(),
            "edge_changes": set()}
        for c in SEMANTIC_CATEGORIES}

    def _hit(cat: str, node: str | None = None, fact_ids=(), edge=None):
        d = out[cat]
        d["changed"] = True
        if node:
            d["nodes"].add(node)
        d["fact_ids"].update(fact_ids)
        if edge:
            d["edge_changes"].add(edge)

    be_map = {e: before.edges[e] for e in before.edges}
    ae_map = {e: after.edges[e] for e in after.edges}
    for ek in sorted(set(after.edges) - set(before.edges)):
        e = ae_map[ek]
        cats = _EDGE_KIND_CATEGORIES.get(e.kind, set())
        for c in cats:
            _hit(c, ek, e.source_fact_ids, f"+{ek}:{e.kind}")
    for ek in sorted(set(before.edges) - set(after.edges)):
        e = be_map[ek]
        for c in _EDGE_KIND_CATEGORIES.get(e.kind, set()):
            _hit(c, ek, e.source_fact_ids, f"-{ek}:{e.kind}")

    for nid in sorted(set(before.nodes) | set(after.nodes)):
        b, a = before.nodes.get(nid), after.nodes.get(nid)
        if b is None or a is None:
            node = a or b
            fids = _node_fact_ids(node)
            for c, kinds in _NODE_KIND_CATEGORIES.items():
                if node.kind in kinds:
                    _hit(c, nid, fids)
            continue
        if b.to_dict() == a.to_dict():
            continue
        fids = _node_fact_ids(a) + _node_fact_ids(b)
        for c, kinds in _NODE_KIND_CATEGORIES.items():
            if a.kind in kinds:
                _hit(c, nid, fids)
        keys = set(b.attrs) | set(a.attrs)
        for k in keys:
            if b.attrs.get(k) == a.attrs.get(k):
                continue
            for c, names in _ATTR_CATEGORIES.items():
                if any(n in k for n in names):
                    _hit(c, nid, fids)
    return {c: {"changed": d["changed"], "nodes": sorted(d["nodes"]),
                "fact_ids": sorted(d["fact_ids"]),
                "edge_changes": sorted(d["edge_changes"])}
            for c, d in out.items()}


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
    sem = _semantic_diff(before, after, changed_nodes)
    return {
        "nodes_added": sorted(an - bn), "nodes_removed": sorted(bn - an),
        "nodes_changed": changed_nodes,
        "edges_added": sorted(ae - be), "edges_removed": sorted(be - ae),
        "security_changed": flags["external_exposure_changed"]
            or flags["unprotected_changed"] or sem["security"]["changed"],
        "ownership_changed": flags["ownership_gaps_changed"]
            or sem["ownership"]["changed"],
        "cost_changed": flags["unallocated_cost_changed"]
            or sem["cost"]["changed"],
        "observability_changed": flags["unmonitored_changed"]
            or sem["slo"]["changed"],
        "semantic": sem,
        "gap_deltas": flags,
        "blast_radius_delta": br_delta,
        "hash_before": before.graph_hash, "hash_after": after.graph_hash,
    }
