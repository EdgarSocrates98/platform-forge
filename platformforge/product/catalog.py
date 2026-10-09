"""Platform catalog — catalog-info.yaml / Component / API / Resource /
System / Domain entities → facts + ownership/dependency edges."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from platformforge.models.base import stable_id

_KIND_MAP = {"Component": "component", "API": "api", "Resource": "service",
             "System": "component", "Domain": "component",
             "Group": "team", "User": "owner", "Location": "repository"}


def analyze_catalog(path: str | Path) -> dict[str, Any]:
    root = Path(path)
    files = (sorted(root.rglob("catalog-info.y*ml")) +
             [p for p in sorted(root.rglob("*.yaml"))
              if "catalog" in p.name]) if root.is_dir() else [root]
    facts: list[dict[str, Any]] = []
    for f in sorted(set(files)):
        try:
            docs = [d for d in yaml.safe_load_all(f.read_text())
                    if isinstance(d, dict) and "backstage.io" in
                    str(d.get("apiVersion", ""))]
        except yaml.YAMLError:
            continue
        for doc in docs:
            kind = doc.get("kind", "Component")
            meta = doc.get("metadata") or {}
            spec = doc.get("spec") or {}
            name, ns = meta.get("name", "?"), meta.get("namespace", "default")
            nk = _KIND_MAP.get(kind, "component")
            label = f"{ns}/{name}"
            edges = []
            owner = spec.get("owner")
            if owner:
                edges.append({"src_kind": "team", "src": str(owner),
                              "dst_kind": nk, "dst": label,
                              "kind": "owns"})
            for dep in spec.get("dependsOn") or []:
                t = str(dep).split(":")[-1]
                edges.append({"src_kind": nk, "src": label,
                              "dst_kind": "component", "dst": t,
                              "kind": "depends_on"})
            if spec.get("system"):
                edges.append({"src_kind": nk, "src": label,
                              "dst_kind": "component",
                              "dst": str(spec["system"]),
                              "kind": "contained_by"})
            for api in spec.get("providesApis") or []:
                edges.append({"src_kind": nk, "src": label,
                              "dst_kind": "api", "dst": str(api),
                              "kind": "exposes"})
            for api in spec.get("consumesApis") or []:
                edges.append({"src_kind": nk, "src": label,
                              "dst_kind": "api", "dst": str(api),
                              "kind": "consumes"})
            attrs = {"entity_kind": kind, "name": name, "namespace": ns,
                     "type": spec.get("type"), "lifecycle": spec.get("lifecycle"),
                     "owner": owner, "system": spec.get("system"),
                     "annotations": meta.get("annotations") or {},
                     "tags": meta.get("tags") or [],
                     "graph": {"nodes": [{"kind": nk, "label": label,
                                          "attrs": {"type": spec.get("type")}}],
                               "edges": edges}}
            facts.append({"fact_id": stable_id("PF-CAT", kind, f"{ns}/{name}"),
                          "kind": "catalog.entity", "source": str(f),
                          "location": f"{ns}/{name}", "tier": 3,
                          "attrs": attrs})
    return {"facts": facts, "counts": {"entities": len(facts)}}
