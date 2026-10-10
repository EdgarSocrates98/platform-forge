"""Platform Forge → ForgeGraphView/v1 adapter.

Maps the real ``platformforge.graph`` engine (nodes/edges with
provenance + temporal windows + fact ids) onto the view contract. The
engine stays authoritative — this only projects it for viewing.
"""

from __future__ import annotations

from pathlib import Path

from platformforge._graphview import (
    ForgeGraphView,
    GraphEdgeView,
    GraphNodeView,
    new_descriptor,
)

PROVIDER = "platform-forge"


def build_view(
    root: str | Path = ".", *, snapshot: str | None = None
) -> ForgeGraphView | None:
    """Persisted graph → view. None when the graph/snapshot is absent.

    ``snapshot`` names a hash under ``.forge/graph/snapshots/`` — the
    view then carries that snapshot's stamp on the descriptor.
    """
    from platformforge import graph as G

    try:
        g = G.load_snapshot(root, snapshot) if snapshot else G.load(root)
    except (OSError, ValueError, KeyError, TypeError):
        return None
    desc = new_descriptor(
        provider_id=PROVIDER,
        domain="platform",
        graph_id="platform-graph",
        capabilities=(
            "snapshots",
            "node_inspect",
            "edge_inspect",
            "neighbors",
            "paths",
            "dependency_traversal",
            "impact_analysis",
            "snapshot_diff",
            "temporal",
            "search",
            "filter",
            "export",
        ),
    )
    object.__setattr__(desc, "node_count", len(g.nodes))
    object.__setattr__(desc, "edge_count", len(g.edges))
    if snapshot:
        object.__setattr__(desc, "snapshot_id", snapshot)
    object.__setattr__(
        desc, "available_layers", tuple(sorted({n.kind for n in g.nodes.values()}))
    )
    nodes = tuple(
        GraphNodeView(
            id=n.node_id,
            kind=n.kind,
            label=n.label,
            domain="platform",
            source_provider=PROVIDER,
            attributes=dict(n.attrs),
            epistemic_state="observed",
            evidence_refs=tuple(n.source_fact_ids),
        )
        for n in g.nodes.values()
    )
    edges = tuple(
        GraphEdgeView(
            id=e.eid,
            source=e.src,
            target=e.dst,
            kind=e.kind,
            provenance=e.provenance,
            epistemic_state=e.provenance,
            evidence_refs=tuple(e.source_fact_ids),
            confidence=e.confidence,
            temporal=dict(e.temporal),
        )
        for e in g.edges.values()
    )
    return ForgeGraphView(descriptor=desc, nodes=nodes, edges=edges)


def descriptors(root: str | Path = ".") -> list[dict]:
    view = build_view(root)
    return [view.descriptor.to_dict()] if view else []
