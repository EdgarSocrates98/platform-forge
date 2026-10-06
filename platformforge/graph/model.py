"""Deterministic graph model conforming to contracts/graph.schema.json
(platformforge/graph/v1). Nodes and edges are derived from facts and carry
source_fact_ids; inferred edges are never presented as observed."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from platformforge.core.hashing import sha256_text
from platformforge.graph.vocab import EDGE_KINDS, NODE_KINDS, PROVENANCES, impact_of

SCHEMA = "platformforge/graph/v1"
_SLUG_RE = re.compile(r"[^a-z0-9_.\-/]+")


def node_id(kind: str, label: str) -> str:
    """Deterministic node id: `kind/label` normalized."""
    if kind not in NODE_KINDS:
        raise ValueError(f"unknown node kind: {kind}")
    slug = _SLUG_RE.sub("-", label.strip().lower()).strip("-")
    if not slug:
        raise ValueError("empty node label")
    return f"{kind}/{slug}"


@dataclass(frozen=True)
class Node:
    node_id: str
    kind: str
    label: str
    attrs: dict[str, Any] = field(default_factory=dict)
    source_fact_ids: tuple[str, ...] = ()

    @classmethod
    def make(cls, kind: str, label: str, attrs: dict[str, Any] | None = None,
             fact_ids: Iterable[str] = ()) -> Node:
        return cls(node_id=node_id(kind, label), kind=kind, label=label,
                   attrs=dict(attrs or {}),
                   source_fact_ids=tuple(sorted(set(fact_ids))))

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"node_id": self.node_id, "kind": self.kind,
                             "label": self.label}
        if self.attrs:
            d["attrs"] = self.attrs
        if self.source_fact_ids:
            d["source_fact_ids"] = list(self.source_fact_ids)
        return d


@dataclass(frozen=True)
class Edge:
    src: str
    dst: str
    kind: str
    provenance: str = "declared"
    confidence: float = 1.0
    source_fact_ids: tuple[str, ...] = ()
    attrs: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.kind not in EDGE_KINDS:
            raise ValueError(f"unknown edge kind: {self.kind}")
        if self.provenance not in PROVENANCES:
            raise ValueError(f"bad provenance: {self.provenance}")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError("confidence out of range")

    @property
    def eid(self) -> str:
        return f"{self.src}->{self.dst}:{self.kind}"

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"from": self.src, "to": self.dst,
                             "kind": self.kind, "provenance": self.provenance,
                             "confidence": self.confidence}
        if self.source_fact_ids:
            d["source_fact_ids"] = list(self.source_fact_ids)
        if self.attrs:
            d["attrs"] = self.attrs
        return d


@dataclass
class Graph:
    nodes: dict[str, Node] = field(default_factory=dict)
    edges: dict[str, Edge] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)

    def add_node(self, node: Node) -> Node:
        existing = self.nodes.get(node.node_id)
        if existing:
            merged = Node(existing.node_id, existing.kind, existing.label,
                          attrs={**existing.attrs, **node.attrs},
                          source_fact_ids=tuple(sorted(
                              set(existing.source_fact_ids)
                              | set(node.source_fact_ids))))
            self.nodes[node.node_id] = merged
            return merged
        self.nodes[node.node_id] = node
        return node

    def add_edge(self, edge: Edge) -> Edge:
        if edge.src not in self.nodes or edge.dst not in self.nodes:
            raise ValueError(f"edge endpoint missing: {edge.eid}")
        existing = self.edges.get(edge.eid)
        if existing:
            stronger = existing if existing.confidence >= edge.confidence \
                else edge
            prov_order = {"observed": 2, "declared": 1, "inferred": 0}
            provenance = max(
                (existing.provenance, edge.provenance),
                key=lambda p: prov_order[p])
            merged = Edge(stronger.src, stronger.dst, stronger.kind,
                          provenance=provenance,
                          confidence=stronger.confidence,
                          source_fact_ids=tuple(sorted(
                              set(existing.source_fact_ids)
                              | set(edge.source_fact_ids))),
                          attrs={**existing.attrs, **edge.attrs})
            self.edges[edge.eid] = merged
            return merged
        self.edges[edge.eid] = edge
        return edge

    # ── serialization ─────────────────────────────────────────
    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "nodes": [self.nodes[k].to_dict() for k in sorted(self.nodes)],
            "edges": [self.edges[k].to_dict() for k in sorted(self.edges)],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, indent=2)

    @classmethod
    def from_dict(cls, doc: dict[str, Any]) -> Graph:
        if doc.get("schema") != SCHEMA:
            raise ValueError("not a platformforge/graph/v1 document")
        g = cls()
        for n in doc.get("nodes", []):
            g.nodes[n["node_id"]] = Node(
                node_id=n["node_id"], kind=n["kind"], label=n["label"],
                attrs=n.get("attrs", {}),
                source_fact_ids=tuple(n.get("source_fact_ids", [])))
        for e in doc.get("edges", []):
            g.edges[f"{e['from']}->{e['to']}:{e['kind']}"] = Edge(
                src=e["from"], dst=e["to"], kind=e["kind"],
                provenance=e.get("provenance", "declared"),
                confidence=e.get("confidence", 1.0),
                source_fact_ids=tuple(e.get("source_fact_ids", [])),
                attrs=e.get("attrs", {}))
        return g

    @property
    def graph_hash(self) -> str:
        return sha256_text(json.dumps(self.to_dict(), sort_keys=True))

    def stats(self) -> dict[str, Any]:
        by_kind: dict[str, int] = {}
        for n in self.nodes.values():
            by_kind[n.kind] = by_kind.get(n.kind, 0) + 1
        by_edge: dict[str, int] = {}
        for e in self.edges.values():
            by_edge[e.kind] = by_edge.get(e.kind, 0) + 1
        return {"nodes": len(self.nodes), "edges": len(self.edges),
                "node_kinds": by_kind, "edge_kinds": by_edge,
                "graph_hash": self.graph_hash}


def impact_class(edge_kind: str) -> str:
    return impact_of(edge_kind)
