"""§100–101 IAM v2 — identity paths over the graph.

Four questions Graphfy must answer:

  who can become this role?
  who can access this resource?
  what workloads use this identity?
  blast radius of compromising it?

Paths are evidence: every hop cites fact_ids. "No path found" is
reported, never "no risk" — absence of evidence is named as such.
"""

from __future__ import annotations

from typing import Any

from platformforge.graph.model import Graph

_ASSUME = {"assumes", "impersonates", "can_access"}
_WILDCARD = {"wildcard-principal", "wildcard", "*"}


def _targets(graph: Graph, name: str, kind: str | None = None) -> set[str]:
    """Resolve a user-supplied name to node-id candidates: exact id,
    kind-prefixed id, and any node whose id ends with /name."""
    cands = {name}
    if kind:
        cands.add(f"{kind}/{name}")
    cands |= {nid for nid in graph.nodes
              if nid == name or nid.endswith(f"/{name}")}
    return cands


def who_can_become(graph: Graph, role: str) -> dict[str, Any]:
    """Principals with an `assumes`/`impersonates` edge into `role`."""
    targets = _targets(graph, role, "role")
    hits = []
    for e in graph.edges.values():
        if e.dst in targets and e.kind in ("assumes", "impersonates"):
            hits.append({"principal": e.src,
                         "via": e.kind, "fact_ids": e.source_fact_ids})
    return {"role": role, "can_become": hits,
            "count": len(hits),
            "status": "measured" if hits else "no-path-found"}


def who_can_access(graph: Graph, resource: str) -> dict[str, Any]:
    """Principals/policies with can_access into the resource."""
    targets = _targets(graph, resource)
    hits = []
    for e in graph.edges.values():
        if e.dst in targets and e.kind in _ASSUME:
            hits.append({"principal": e.src, "via": e.kind,
                         "fact_ids": e.source_fact_ids})
    return {"resource": resource, "can_access": hits, "count": len(hits),
            "status": "measured" if hits else "no-path-found"}


def workloads_using_identity(graph: Graph, identity: str) -> dict[str, Any]:
    """Workloads with `assumes`/`uses_secret` into the identity."""
    targets = _targets(graph, identity)
    hits = []
    for e in graph.edges.values():
        if e.dst in targets and \
                e.kind in ("assumes", "uses_secret") and \
                e.src.startswith(("workload/", "pod/")):
            hits.append({"workload": e.src, "via": e.kind,
                         "fact_ids": e.source_fact_ids})
    return {"identity": identity, "workloads": hits, "count": len(hits),
            "status": "measured" if hits else "no-path-found"}


def compromise_blast(graph: Graph, identity: str) -> dict[str, Any]:
    """Blast radius if `identity` is compromised — everything reachable
    via assumes/can_access/uses_secret downstream."""
    from platformforge.graph.query import blast_radius
    targets = _targets(graph, identity)
    nid = next(iter(targets & set(graph.nodes)), identity)
    br = blast_radius(graph, nid)
    return {"identity": identity, "blast": br,
            "status": "measured" if br["nodes"] else "no-path-found",
            "note": "compromise blast = transitive reachability; "
                    "not a likelihood estimate"}
