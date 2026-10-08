"""Backstage catalog-info analyzer — catalog entities as declared facts.

Per file: component/api/resource entities with kind, owner, lifecycle,
system, dependencies. Read-only — never calls a Backstage API.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from platformforge.models.base import stable_id


def analyze_backstage(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    files = [p] if p.is_file() else sorted(
        p.rglob("catalog-info.y*ml"))
    facts: list[dict[str, Any]] = []
    for f in files:
        try:
            docs = list(yaml.safe_load_all(f.read_text()))
        except yaml.YAMLError:
            continue
        for doc in docs:
            if not isinstance(doc, dict) or "apiVersion" not in doc:
                continue
            meta = doc.get("metadata") or {}
            spec = doc.get("spec") or {}
            facts.append({
                "fact_id": stable_id(
                    "backstage", str(f), str(meta.get("name", ""))),
                "kind": "catalog.entity",
                "source": str(f),
                "location": str(meta.get("name", f.name)),
                "tier": 3,
                "attrs": {
                    "entity_kind": doc.get("kind", ""),
                    "api_version": doc.get("apiVersion", ""),
                    "owner": spec.get("owner", ""),
                    "lifecycle": spec.get("lifecycle", ""),
                    "system": spec.get("system", ""),
                    "type": spec.get("type", ""),
                    "depends_on": list(spec.get("dependsOn") or []),
                    "provides_apis": list(spec.get("providesApis") or []),
                    "consumes_apis": list(spec.get("consumesApis") or []),
                    "has_owner": bool(spec.get("owner")),
                }})
    return {"facts": facts}
