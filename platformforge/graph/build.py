"""GraphBuilder — facts in, provenanced graph out.

Domain analyzers (Terraform, Kubernetes, …) emit Facts; a fact may declare
graph contributions under `attrs["graph"]`:

    {"graph": {
        "nodes": [{"kind": "workload", "label": "payments", "attrs": {...}}],
        "edges": [{"src_kind": "workload", "src": "payments",
                   "dst_kind": "secret", "dst": "db-creds",
                   "kind": "uses_secret"}]}}

Edges inherit the fact's tier as provenance (t1/t2 → observed, t3 → declared,
t4 → inferred) and always carry the fact_id — the graph is derived from
evidence, never guessed.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, ClassVar

from platformforge.graph.model import Edge, Graph, Node, node_id
from platformforge.graph.vocab import PROVENANCES


def _tier_provenance(tier: int | str) -> str:
    """EvidenceTier int → edge provenance (§4): 0-1 observed (measured,
    provider), 2 planned (generated plan — never observed), 3-5 declared,
    6-7 inferred."""
    t = {f"t{i}": i for i in range(8)}.get(tier, tier)
    try:
        t = int(t)
    except (TypeError, ValueError):
        return "declared"
    if t <= 1:
        return "observed"
    return {2: "planned"}.get(t, "declared" if t <= 5 else "inferred")


class GraphBuilder:
    def __init__(self):
        self.graph = Graph()

    def add_node(self, kind: str, label: str,
                 attrs: dict[str, Any] | None = None,
                 fact_ids: Iterable[str] = ()) -> Node:
        return self.graph.add_node(
            Node.make(kind, label, attrs, fact_ids))

    def add_edge(self, src_kind: str, src_label: str, dst_kind: str,
                 dst_label: str, kind: str, provenance: str = "declared",
                 confidence: float = 1.0,
                 fact_ids: Iterable[str] = (),
                 attrs: dict[str, Any] | None = None) -> Edge:
        if provenance not in PROVENANCES:
            raise ValueError(f"bad provenance: {provenance}")
        s, d = node_id(src_kind, src_label), node_id(dst_kind, dst_label)
        for nid, k, lbl in ((s, src_kind, src_label),
                            (d, dst_kind, dst_label)):
            if nid not in self.graph.nodes:
                self.add_node(k, lbl)
        return self.graph.add_edge(
            Edge(src=s, dst=d, kind=kind, provenance=provenance,
                 confidence=confidence,
                 source_fact_ids=tuple(sorted(set(fact_ids))),
                 attrs=dict(attrs or {})))

    # §5: node state is resolved from the strongest contributing fact —
    # observed beats planned beats desired(declared) beats inferred.
    _STATE_ORDER: ClassVar[dict[str, int]] = {
        "observed": 0, "planned": 1, "desired": 2, "inferred": 3}
    _PROV_STATE: ClassVar[dict[str, str]] = {
        "observed": "observed", "planned": "planned",
        "declared": "desired", "inferred": "inferred"}

    def from_facts(self, facts: Iterable[dict[str, Any]]) -> GraphBuilder:
        facts = list(facts)  # consumed twice: fact edges + delivery joins
        state_rank: dict[str, int] = {}
        for f in facts:
            contrib = (f.get("attrs") or {}).get("graph") or {}
            fid = f.get("fact_id", "")
            prov = _tier_provenance(f.get("tier", 3))
            for n in contrib.get("nodes", []):
                node = self.add_node(n["kind"], n["label"], n.get("attrs"),
                                     [fid] if fid else [])
                rank = self._STATE_ORDER[self._PROV_STATE[prov]]
                if rank < state_rank.get(node.node_id, 99):
                    state_rank[node.node_id] = rank
                    node.attrs["state"] = self._PROV_STATE[prov]
            for e in contrib.get("edges", []):
                self.add_edge(e["src_kind"], e["src"], e["dst_kind"],
                              e["dst"], e["kind"],
                              provenance=e.get("provenance", prov),
                              confidence=e.get("confidence", 1.0),
                              fact_ids=[fid] if fid else [],
                              attrs=e.get("attrs"))
        self._delivery(facts)
        return self

    def _delivery(self, facts: Iterable[dict[str, Any]]) -> None:
        """§72 — join gitops/workflows/workloads into the delivery chain."""
        from platformforge.graph.delivery import delivery_edges
        for e in delivery_edges(list(facts)):
            self.add_edge(e["src_kind"], e["src"], e["dst_kind"], e["dst"],
                          e["kind"], provenance="declared",
                          fact_ids=e.get("fact_ids") or [],
                          attrs={"via": e.get("via")})
