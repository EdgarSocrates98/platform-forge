"""Cycle 5 §32–35 — pluggable graph storage.

`GraphBackend` is a narrow contract: put/get/del nodes & edges,
iterate, count. `MemoryBackend` preserves today's behaviour;
`SQLiteBackend` gives a local indexed baseline for larger graphs.
An external graph DB would be an adapter implementing the same
contract — never hardwired (§35).

The canonical representation stays provider-neutral `Graph`
(document dicts); backends are storage detail.
"""

from __future__ import annotations

import json
import sqlite3
from abc import ABC, abstractmethod
from pathlib import Path

from platformforge.graph.model import Edge, Graph, Node


class GraphBackend(ABC):
    @abstractmethod
    def put_graph(self, graph: Graph, name: str = "default") -> None: ...
    @abstractmethod
    def get_graph(self, name: str = "default") -> Graph: ...
    @abstractmethod
    def counts(self, name: str = "default") -> dict[str, int]: ...
    @abstractmethod
    def neighbors(self, node_id: str, name: str = "default",
                  direction: str = "both") -> list[Edge]: ...
    @abstractmethod
    def close(self) -> None: ...


class MemoryBackend(GraphBackend):
    """Default: same in-process dict storage as today."""

    def __init__(self):
        self._graphs: dict[str, Graph] = {}

    def put_graph(self, graph: Graph, name: str = "default") -> None:
        self._graphs[name] = graph

    def get_graph(self, name: str = "default") -> Graph:
        return self._graphs.get(name, Graph())

    def counts(self, name: str = "default") -> dict[str, int]:
        g = self.get_graph(name)
        return {"nodes": len(g.nodes), "edges": len(g.edges)}

    def neighbors(self, node_id: str, name: str = "default",
                  direction: str = "both") -> list[Edge]:
        g = self.get_graph(name)
        out = []
        for e in g.edges.values():
            if direction in ("out", "both") and e.src == node_id or direction in ("in", "both") and e.dst == node_id:
                out.append(e)
        return out

    def close(self) -> None:
        pass


_SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes (
  graph TEXT NOT NULL, node_id TEXT NOT NULL, kind TEXT NOT NULL,
  label TEXT NOT NULL, doc TEXT NOT NULL,
  PRIMARY KEY (graph, node_id));
CREATE INDEX IF NOT EXISTS idx_nodes_kind ON nodes(graph, kind);
CREATE TABLE IF NOT EXISTS edges (
  graph TEXT NOT NULL, eid TEXT NOT NULL, src TEXT NOT NULL,
  dst TEXT NOT NULL, kind TEXT NOT NULL, doc TEXT NOT NULL,
  PRIMARY KEY (graph, eid));
CREATE INDEX IF NOT EXISTS idx_edges_src ON edges(graph, src);
CREATE INDEX IF NOT EXISTS idx_edges_dst ON edges(graph, dst);
CREATE INDEX IF NOT EXISTS idx_edges_kind ON edges(graph, kind);
CREATE TABLE IF NOT EXISTS meta (
  graph TEXT PRIMARY KEY, doc TEXT NOT NULL);
"""


class SQLiteBackend(GraphBackend):
    """Local indexed baseline (§34). One file per store; graphs are
    namespaced rows. Adjacency queries hit indexes, not full scans
    (§31)."""

    def __init__(self, path: str | Path):
        self._db = sqlite3.connect(str(path))
        self._db.executescript(_SCHEMA)
        self._db.commit()

    def put_graph(self, graph: Graph, name: str = "default") -> None:
        cur = self._db.cursor()
        cur.execute("DELETE FROM nodes WHERE graph=?", (name,))
        cur.execute("DELETE FROM edges WHERE graph=?", (name,))
        cur.executemany(
            "INSERT INTO nodes VALUES (?,?,?,?,?)",
            [(name, n.node_id, n.kind, n.label,
              json.dumps(n.to_dict(), sort_keys=True))
             for n in graph.nodes.values()])
        cur.executemany(
            "INSERT INTO edges VALUES (?,?,?,?,?,?)",
            [(name, e.eid, e.src, e.dst, e.kind,
              json.dumps(e.to_dict(), sort_keys=True))
             for e in graph.edges.values()])
        cur.execute(
            "INSERT OR REPLACE INTO meta VALUES (?,?)",
            (name, json.dumps(graph.meta, sort_keys=True)))
        self._db.commit()

    def get_graph(self, name: str = "default") -> Graph:
        g = Graph()
        row = self._db.execute(
            "SELECT doc FROM meta WHERE graph=?", (name,)).fetchone()
        if row:
            g.meta.update(json.loads(row[0]))
        for (doc,) in self._db.execute(
                "SELECT doc FROM nodes WHERE graph=?", (name,)):
            n = json.loads(doc)
            g.nodes[n["node_id"]] = Node(
                node_id=n["node_id"], kind=n["kind"], label=n["label"],
                attrs=n.get("attrs", {}),
                source_fact_ids=tuple(n.get("source_fact_ids", ())))
        for (doc,) in self._db.execute(
                "SELECT doc FROM edges WHERE graph=?", (name,)):
            e = json.loads(doc)
            edge = Edge(src=e["from"], dst=e["to"], kind=e["kind"],
                        provenance=e.get("provenance", "declared"),
                        confidence=e.get("confidence", 1.0),
                        source_fact_ids=tuple(e.get("source_fact_ids", ())),
                        attrs=e.get("attrs", {}),
                        evidence=tuple(e.get("evidence", ())),
                        temporal=e.get("temporal", {}))
            g.edges[edge.eid] = edge
        return g

    def counts(self, name: str = "default") -> dict[str, int]:
        n = self._db.execute(
            "SELECT COUNT(*) FROM nodes WHERE graph=?", (name,)).fetchone()
        e = self._db.execute(
            "SELECT COUNT(*) FROM edges WHERE graph=?", (name,)).fetchone()
        return {"nodes": n[0], "edges": e[0]}

    def neighbors(self, node_id: str, name: str = "default",
                  direction: str = "both") -> list[Edge]:
        clauses = {"out": "src=?", "in": "dst=?", "both": "(src=? OR dst=?)"}
        params = [name, node_id] if direction != "both" else \
            [name, node_id, node_id]
        out = []
        for (doc,) in self._db.execute(
                f"SELECT doc FROM edges WHERE graph=? AND "
                f"{clauses[direction]}", params):
            e = json.loads(doc)
            out.append(Edge(src=e["from"], dst=e["to"], kind=e["kind"],
                            provenance=e.get("provenance", "declared"),
                            confidence=e.get("confidence", 1.0),
                            source_fact_ids=tuple(
                                e.get("source_fact_ids", ())),
                            attrs=e.get("attrs", {}),
                            evidence=tuple(e.get("evidence", ())),
                            temporal=e.get("temporal", {})))
        return out

    def close(self) -> None:
        self._db.close()


def open_backend(spec: str | None = None) -> GraphBackend:
    """`memory` (default) or `sqlite:<path>`."""
    if spec and spec.startswith("sqlite:"):
        return SQLiteBackend(spec.split(":", 1)[1])
    return MemoryBackend()
