"""Crossplane — CompositeResourceDefinition / Composition / managed resource
facts + provisioning edges."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from platformforge.models.base import stable_id


def analyze_crossplane(path: str | Path) -> dict[str, Any]:
    root = Path(path)
    files = (sorted(root.rglob("*.yaml")) + sorted(root.rglob("*.yml"))) \
        if root.is_dir() else [root]
    facts: list[dict[str, Any]] = []
    for f in files:
        try:
            for doc in yaml.safe_load_all(f.read_text()):
                if not isinstance(doc, dict) or not doc.get("kind"):
                    continue
                kind = doc["kind"]
                api = str(doc.get("apiVersion", ""))
                meta = doc.get("metadata") or {}
                spec = doc.get("spec") or {}
                name = meta.get("name", "?")
                loc = f"{f}::{name}"
                if "crossplane.io" not in api and \
                        not api.startswith("apiextensions.crossplane.io"):
                    # managed resources carry their own groups (e.g.
                    # *.aws.crossplane.io) — detect via api suffix
                    if ".crossplane.io" not in api:
                        continue
                if kind == "CompositeResourceDefinition":
                    attrs = {"xrd": name,
                             "group": spec.get("group"),
                             "kind_claim": (spec.get("claimNames") or {})
                                 .get("kind"),
                             "versions": [v.get("name")
                                          for v in spec.get("versions") or []],
                             "connection_secret_keys":
                                 spec.get("connectionSecretKeys") or []}
                    fk = "platform.xrd"
                elif kind == "Composition":
                    attrs = {"composition": name,
                             "composite_type": (spec.get("compositeTypeRef")
                                                or {}).get("kind"),
                             "resources": len(spec.get("resources") or []),
                             "pipeline_mode": bool(spec.get("pipeline"))}
                    fk = "platform.composition"
                else:
                    attrs = {"managed_kind": kind, "name": name,
                             "api": api,
                             "for_provider_keys": sorted(
                                 (spec.get("forProvider") or {}).keys())[:20],
                             "deletion_policy": spec.get("deletionPolicy",
                                                         "Delete")}
                    fk = "platform.managed_resource"
                attrs["graph"] = {
                    "nodes": [{"kind": "crossplane_xr",
                               "label": name}],
                    "edges": []}
                facts.append({"fact_id": stable_id("PF-XR", fk, loc),
                              "kind": fk, "source": str(f), "location": loc,
                              "tier": 3, "attrs": attrs})
        except yaml.YAMLError:
            continue
    return {"facts": facts, "counts": {"facts": len(facts)}}
