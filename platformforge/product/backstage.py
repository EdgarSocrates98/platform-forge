"""Backstage adapter — project the platform graph into Backstage catalog
entities. PROJECTION ONLY: Backstage is never the canonical source."""

from __future__ import annotations

from typing import Any

from platformforge.graph.model import Graph


def to_backstage(graph: Graph) -> dict[str, Any]:
    """Graph → Backstage entity docs (Component/API/Resource/Group/Domain)."""
    kind_map = {"component": "Component", "service": "Component",
                "workload": "Component", "api": "API", "team": "Group",
                "owner": "User", "database": "Resource", "queue": "Resource",
                "bucket": "Resource", "cluster": "Resource",
                "domain": "Domain"}
    entities = []
    for n in sorted(graph.nodes.values(), key=lambda n: n.node_id):
        bk = kind_map.get(n.kind)
        if not bk:
            continue
        name = n.label.split("/")[-1].replace("_", "-").lower()
        meta: dict[str, Any] = {"name": name,
                                "annotations": {"platformforge/node_id":
                                                n.node_id}}
        if "/" in n.label:
            meta["namespace"] = n.label.split("/")[0]
        spec: dict[str, Any] = {}
        owners = [e.src for e in graph.edges.values()
                  if e.dst == n.node_id and e.kind == "owns"]
        if owners:
            spec["owner"] = owners[0].split("/")[-1]
        deps = [e.dst for e in graph.edges.values()
                if e.src == n.node_id and e.kind == "depends_on"]
        if deps:
            spec["dependsOn"] = sorted(deps)
        provides = [e.dst.split("/")[-1] for e in graph.edges.values()
                    if e.src == n.node_id and e.kind == "exposes"
                    and e.dst.startswith("api/")]
        if provides:
            spec["providesApis"] = sorted(provides)
        entities.append({"apiVersion": "backstage.io/v1alpha1",
                         "kind": bk, "metadata": meta,
                         "spec": {**spec, "type": n.attrs.get("type",
                                                              "service")}})
    return {"entities": entities, "counts": {"entities": len(entities)},
            "note": "projection — canonical truth stays in the platform "
                    "graph; do not hand-edit and expect parity"}
