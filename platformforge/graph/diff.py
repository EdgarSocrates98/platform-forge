"""Graph diff: before/after comparison feeding the change-risk engine."""

from __future__ import annotations

from collections import deque
from typing import Any

from platformforge.graph.model import Graph
from platformforge.graph.query import DEPENDENCY_KINDS, _adj, gaps

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


def _descendants(fwd: dict[str, list], nid: str) -> set[str]:
    """Forward reachability over dependency edges — {nid} ∪ deps*(nid)."""
    seen = {nid}
    q = deque([nid])
    while q:
        for e in fwd.get(q.popleft(), []):
            if e.dst not in seen:
                seen.add(e.dst)
                q.append(e.dst)
    return seen


def _cone_size(rev: dict[str, list], nid: str) -> int:
    """impacted_total without per-node bookkeeping — count of all srcs
    reachable backward (dependents cone)."""
    seen = {nid}
    q = deque([nid])
    while q:
        for e in rev.get(q.popleft(), []):
            if e.src not in seen:
                seen.add(e.src)
                q.append(e.src)
    return len(seen) - 1


def _cone_map(g: Graph, rev: dict[str, list]) -> dict[str, int]:
    """impacted_total for every node via SCC condensation: nodes in one
    SCC share an ancestor set, so ancestors resolve once per SCC —
    ancestor masks as int bitsets, computed in one iterative
    post-order pass over the condensed DAG."""
    from platformforge.graph.query import condensation
    scc_of, members, rev_scc = condensation(g)
    # Kahn order: an SCC's parents (ancestors) are strictly before it in
    # rev_scc's dependency direction — process sources first so every
    # mask is complete when read.
    children: dict[int, list[int]] = {s: [] for s in rev_scc}
    indeg = {s: len(ps) for s, ps in rev_scc.items()}
    for s, ps in rev_scc.items():
        for p in ps:
            children[p].append(s)
    q = deque(s for s, d in indeg.items() if d == 0)
    anc: dict[int, int] = {}
    while q:
        u = q.popleft()
        m = 1 << u
        for p in rev_scc[u]:
            m |= anc[p]
        anc[u] = m
        for c in children[u]:
            indeg[c] -= 1
            if indeg[c] == 0:
                q.append(c)
    size_of = {i: len(m) for i, m in enumerate(members)}
    # one ancestor-scan per SCC, not per node — nodes in a shared SCC
    # share the ancestor set (freeze dogfood: per-node scans made dense
    # 100k-node diffs quadratic in wall-clock terms)
    total_of_scc = {s: sum(size_of[i] for i in _bits(anc[s]))
                    for s in scc_of.values()}
    return {nid: total_of_scc[s] - 1 for nid, s in scc_of.items()}


def _bits(x: int):
    i = 0
    while x:
        if x & 1:
            yield i
        x >>= 1
        i += 1


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
    # graph_hash covers full to_dict() — equal hashes mean identical
    # serializations, so every diff field is empty by construction.
    # The hashes are output fields anyway, so the fast path is free.
    hb, ha = before.graph_hash, after.graph_hash
    if hb == ha:
        sem = {c: {"changed": False, "nodes": [], "fact_ids": [],
                   "edge_changes": []} for c in SEMANTIC_CATEGORIES}
        return {
            "nodes_added": [], "nodes_removed": [], "nodes_changed": [],
            "edges_added": [], "edges_removed": [],
            "security_changed": False, "ownership_changed": False,
            "cost_changed": False, "observability_changed": False,
            "semantic": sem,
            "gap_deltas": {k + "_changed": False for k in
                           ("external_exposure", "ownership_gaps",
                            "unmonitored", "unprotected",
                            "unallocated_cost")} | {
                k + "_delta": {"added": [], "removed": []} for k in
                ("external_exposure", "ownership_gaps", "unmonitored",
                 "unprotected", "unallocated_cost")},
            "blast_radius_delta": {},
            "hash_before": hb, "hash_after": ha,
        }
    bn, an = set(before.nodes), set(after.nodes)
    be, ae = set(before.edges), set(after.edges)
    changed_nodes = sorted(
        n for n in bn & an
        if before.nodes[n].to_dict() != after.nodes[n].to_dict())
    if bn == an and be == ae and not changed_nodes:
        # identical node/edge/attr structure — gap sets are equal by
        # construction; skip two full sweeps + Tarjan (freeze dogfood:
        # gaps() dominated no-op diffs at 100k nodes)
        empty = {k: [] for k in ("external_exposure", "ownership_gaps",
                                 "unmonitored", "unprotected",
                                 "unallocated_cost")}
        g_before = g_after = empty
    else:
        g_before, g_after = gaps(before), gaps(after)
    flags: dict[str, Any] = {}
    for key in ("external_exposure", "ownership_gaps", "unmonitored",
                "unprotected", "unallocated_cost"):
        flags[key + "_changed"] = g_before[key] != g_after[key]
        flags[key + "_delta"] = {
            "added": sorted(set(g_after[key]) - set(g_before[key])),
            "removed": sorted(set(g_before[key]) - set(g_after[key])),
        }
    # blast-radius deltas — incremental (§211). impacted_total(n) is pure
    # structure: it changes only for n reachable *forward* (depends_on
    # direction) from the dst of a changed dependency edge. Attr-only
    # changes and untouched regions are skipped — the delta is identical.
    fwd_b = _adj(before, kinds=DEPENDENCY_KINDS)
    fwd_a = _adj(after, kinds=DEPENDENCY_KINDS)
    candidates: set[str] = set()
    for ek in be - ae:
        e = before.edges[ek]
        if e.kind in DEPENDENCY_KINDS:
            candidates |= _descendants(fwd_b, e.dst)
    for ek in ae - be:
        e = after.edges[ek]
        if e.kind in DEPENDENCY_KINDS:
            candidates |= _descendants(fwd_a, e.dst)
    rev_b = _adj(before, reverse=True, kinds=DEPENDENCY_KINDS)
    rev_a = _adj(after, reverse=True, kinds=DEPENDENCY_KINDS)
    need = candidates & (bn & an)
    if len(need) * 4 > len(bn & an):
        # dense change — pay the condensation once, then O(SCC) per node
        cones_b = _cone_map(before, rev_b)
        cones_a = _cone_map(after, rev_a)
        sizes_b = {n: cones_b[n] for n in need}
        sizes_a = {n: cones_a[n] for n in need}
    else:
        sizes_b = {n: _cone_size(rev_b, n) for n in need}
        sizes_a = {n: _cone_size(rev_a, n) for n in need}
    br_delta = {}
    for n in sorted(need):
        b, a = sizes_b[n], sizes_a[n]
        if b != a:
            br_delta[n] = {"before": b, "after": a}
    sem = ({c: {"changed": False, "nodes": [], "fact_ids": [],
                "edge_changes": []} for c in SEMANTIC_CATEGORIES}
           if bn == an and be == ae and not changed_nodes
           else _semantic_diff(before, after, changed_nodes))
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
