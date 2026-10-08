"""Explicit graph document migration: platformforge/graph/v1 → v2.

§94 — migration is a declared operation: it produces a new document
(new content hash), stamps `migrated_from`, and never edits v1
artifacts in place. Round-trip: v1 → v2 → v1 must return the original
edge content (evidence/temporal added by the migration is dropped on
downgrade; everything else preserved).
"""

from __future__ import annotations

import time
from typing import Any

from platformforge.graph.model import SCHEMA, SCHEMA_V2, Graph


def migrate_doc_v1_to_v2(doc: dict[str, Any]) -> dict[str, Any]:
    """Return a v2 copy of a v1 graph document."""
    if doc.get("schema") != SCHEMA:
        raise ValueError(f"expected {SCHEMA}, got {doc.get('schema')}")
    out = dict(doc)
    out["schema"] = SCHEMA_V2
    out["migrated_from"] = SCHEMA
    out["migrated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    edges = []
    for e in doc.get("edges", []):
        ne = dict(e)
        if "evidence" not in ne:
            ne["evidence"] = [{
                "provenance": ne.get("provenance", "declared"),
                "fact_ids": list(ne.get("source_fact_ids", []))}]
        edges.append(ne)
    out["edges"] = edges
    return out


def migrate_graph(graph: Graph) -> Graph:
    """Migrate a Graph object to v2 by materializing evidence records
    on every edge. No-op if already fully layered."""
    if not any(e.evidence or e.temporal for e in graph.edges.values()):
        doc = migrate_doc_v1_to_v2(graph.to_dict(schema=SCHEMA))
        return Graph.from_dict(doc)
    return graph
