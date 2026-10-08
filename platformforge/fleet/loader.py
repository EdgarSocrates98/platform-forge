"""Cycle 5 — fleet directory loader (shared by CLI + lab).

A fleet directory is a bounded, offline input bundle:

    fleet.yaml      members (Fleet.from_dict doc)
    graph.yaml      nodes/edges (org + technical)
    events.yaml     {source: [events]} for HistoryEngine
    costs.yaml      cost facts + utilization + denominators
    capacity.yaml   per-member capacity dimensions + observations
    requests.yaml   golden-path requests/outcomes/escapes
    policies.yaml   decisions/exceptions/overrides/outcomes

All files optional — missing inputs keep their analytics `unknown`,
never silently zero.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from platformforge.fleet.models import Fleet
from platformforge.graph.model import Edge, Graph, Node

FLEET_FILES = ("fleet", "graph", "events", "costs", "capacity",
               "requests", "policies")


def load_fleet_dir(path) -> dict[str, Any]:
    """Load every present `<name>.yaml`; missing → None."""
    fx = Path(path)
    if not fx.is_dir():
        raise FileNotFoundError(f"fleet dir not found: {fx}")
    out: dict[str, Any] = {}
    for name in FLEET_FILES:
        p = fx / f"{name}.yaml"
        out[name] = yaml.safe_load(p.read_text()) if p.exists() else None
    return out


def fleet_from(data: dict[str, Any]) -> Fleet:
    doc = data.get("fleet") or {}
    return Fleet.from_dict(doc) if doc.get("fleet_id") \
        else Fleet(fleet_id=doc.get("fleet_id", "fleet"))


def graph_from_doc(doc: dict[str, Any] | None) -> Graph:
    """nodes/edges YAML → Graph; edge endpoints auto-materialize."""
    g = Graph()
    for n in (doc or {}).get("nodes", []):
        g.add_node(Node.make(n["kind"], n["id"], attrs=n.get("attrs", {}),
                             fact_ids=n.get("fact_ids", ())))
    for e in (doc or {}).get("edges", []):
        for nid in (e["src_id"], e["dst_id"]):
            if nid not in g.nodes:
                kind, _, label = nid.partition("/")
                try:
                    g.add_node(Node.make(kind, label or nid))
                except ValueError:
                    break
        else:
            g.add_edge(Edge(e["src_id"], e["dst_id"], e["kind"],
                            provenance=e.get("provenance", "declared"),
                            source_fact_ids=tuple(e.get("fact_ids", ()))))
    return g


def load_fleet(path) -> tuple[Fleet, Graph, dict[str, Any]]:
    """Convenience: dir → (Fleet, Graph, raw docs)."""
    data = load_fleet_dir(path)
    return fleet_from(data), graph_from_doc(data.get("graph")), data
