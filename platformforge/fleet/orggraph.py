"""Cycle 5 Phase B — organizational graph projection (§17–22, §26).

The org graph is a *layered* projection, never merged with the tech
graph: each node belongs to exactly one layer (§20–21) and every
federated node/edge preserves source member + fact ids (§26).

Layers (§21): organization / platform-product / application /
infrastructure / runtime / operations / cost / policy.
"""

from __future__ import annotations

from typing import Any

from platformforge.fleet.models import Fleet, member_key
from platformforge.graph.model import Edge, Graph, Node

LAYERS = ("organization", "platform-product", "application",
          "infrastructure", "runtime", "operations", "cost", "policy")

# node kind → owning layer (§21). Kinds not listed default to the tech
# graph's own layer — the org projection only materializes the org ones.
KIND_LAYER = {
    "organization": "organization", "business_unit": "organization",
    "team": "organization", "domain": "organization",
    "fleet": "organization", "environment": "organization",
    "platform": "platform-product",
    "platform_capability": "platform-product",
    "golden_path": "platform-product", "product": "platform-product",
    "operation_class": "platform-product",
    "service": "application", "api": "application",
    "repository": "application", "component": "application",
    "workload": "application", "model": "application",
    "inference_service": "application", "vector_store": "application",
    "cluster": "infrastructure", "node_pool": "infrastructure",
    "cloud_account": "infrastructure", "region": "infrastructure",
    "database": "infrastructure", "gpu_pool": "infrastructure",
    "accelerator": "infrastructure", "training_job": "infrastructure",
    "model_endpoint": "infrastructure",
    "pod": "runtime", "namespace": "runtime", "flow": "runtime",
    "operation": "operations", "change_intent": "operations",
    "approval": "operations", "rollback": "operations",
    "runbook": "operations", "platform_request": "operations",
    "cost_unit": "cost", "cost_center": "cost", "budget": "cost",
    "billing_unit": "cost",
    "policy": "policy", "security_policy": "policy",
    "admission_policy": "policy", "policy_decision": "policy",
}

# org edge kinds that cross layers explicitly
ORG_EDGES = ("owns", "consumes", "provides", "operates", "supports",
             "funded_by", "depends_on", "governed_by", "uses_capability",
             "uses_golden_path", "escapes_golden_path", "affected_by",
             "shares_runtime_with")


def layer_of(kind: str) -> str:
    return KIND_LAYER.get(kind, "infrastructure")


def project_fleet(fleet: Fleet,
                  member_graphs: dict[str, Graph] | None = None,
                  *,
                  org_edges: list[dict[str, Any]] | None = None) -> Graph:
    """Project a Fleet into an organizational graph (§17–19, §26).

    - fleet/org/env/team/service members become org-layer nodes;
    - member tech graphs merge in with `source_member` provenance;
    - declared org edges (owns/uses_golden_path/…) attach by canonical id.
    """
    g = Graph()
    g.meta["layer"] = "organizational"
    g.meta["fleet_id"] = fleet.fleet_id
    if fleet.organization:
        g.add_node(Node.make("organization", fleet.organization))
    g.add_node(Node.make("fleet", fleet.fleet_id))
    for env in fleet.environments:
        g.add_node(Node.make("environment", env))
    for m in fleet.members:
        kind = {"cluster": "cluster", "cloud_account": "cloud_account",
                "repository": "repository", "service": "service",
                "team": "team", "environment": "environment",
                "subscription": "subscription", "project": "project",
                "region": "region"}.get(m.kind, "component")
        node = Node.make(kind, member_key(m.kind, m.canonical_id),
                         attrs={"name": m.name or m.canonical_id,
                                "environment": m.environment,
                                "team": m.team, "region": m.region,
                                "labels": m.labels})
        g.add_node(node)
        # fleet contains every member; environment scopes it
        g.add_edge(Edge(g.nodes[f"fleet/{fleet.fleet_id}"].node_id,
                        node.node_id, "contained_by",
                        provenance="declared"))
        if m.environment:
            env_id = f"environment/{m.environment.lower()}"
            if env_id in g.nodes:
                g.add_edge(Edge(node.node_id, env_id, "contained_by",
                                provenance="declared"))
    # member tech graphs merge with per-member provenance (§26)
    for member_id, mg in (member_graphs or {}).items():
        for n in mg.nodes.values():
            g.add_node(Node(n.node_id, n.kind, n.label,
                            attrs={**n.attrs, "source_member": member_id},
                            source_fact_ids=n.source_fact_ids))
        for e in mg.edges.values():
            if e.src in g.nodes and e.dst in g.nodes:
                g.add_edge(Edge(e.src, e.dst, e.kind,
                                provenance=e.provenance,
                                confidence=e.confidence,
                                source_fact_ids=e.source_fact_ids,
                                attrs={**e.attrs,
                                       "source_member": member_id}))
    # declared org edges by canonical id: {src_kind, src_id, kind,
    # dst_kind, dst_id, provenance}
    for oe in org_edges or []:
        src = Node.make(oe["src_kind"], oe["src_id"]).node_id
        dst = Node.make(oe["dst_kind"], oe["dst_id"]).node_id
        if src not in g.nodes:
            g.add_node(Node.make(oe["src_kind"], oe["src_id"]))
        if dst not in g.nodes:
            g.add_node(Node.make(oe["dst_kind"], oe["dst_id"]))
        g.add_edge(Edge(src, dst, oe["kind"],
                        provenance=oe.get("provenance", "declared"),
                        confidence=oe.get("confidence", 1.0),
                        source_fact_ids=tuple(oe.get("fact_ids", ()))))
    return g


def layer_view(graph: Graph, layer: str) -> Graph:
    """§20–21 — a single layer's nodes + intra-layer edges."""
    out = Graph()
    out.meta.update(graph.meta)
    out.meta["layer"] = layer
    keep = {nid for nid, n in graph.nodes.items()
            if layer_of(n.kind) == layer}
    for nid in keep:
        out.nodes[nid] = graph.nodes[nid]
    for e in graph.edges.values():
        if e.src in keep and e.dst in keep:
            out.edges[e.eid] = e
    return out


def cross_layer_path(graph: Graph, src: str, dst: str,
                     max_depth: int = 8) -> list[dict[str, Any]]:
    """§22 — cross-layer path query (e.g. team → service → cluster →
    cost center). BFS over all edge kinds, direction-aware."""
    from collections import deque
    adj: dict[str, list[Edge]] = {}
    for e in graph.edges.values():
        adj.setdefault(e.src, []).append(e)
        adj.setdefault(e.dst, []).append(e)   # undirected for tracing
    seen = {src}
    q = deque([(src, [])])
    while q:
        cur, path = q.popleft()
        if cur == dst:
            return path
        if len(path) >= max_depth:
            continue
        for e in adj.get(cur, []):
            nxt = e.dst if e.src == cur else e.src
            if nxt in seen:
                continue
            seen.add(nxt)
            q.append((nxt, path + [{
                "node": nxt, "kind": e.kind,
                "layer": layer_of(graph.nodes[nxt].kind),
                "direction": "out" if e.src == cur else "in",
                "provenance": e.provenance}]))
    return []
