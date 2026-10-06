"""Terraform/OpenTofu plan JSON and state JSON analyzers (offline dumps)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from platformforge.models.base import stable_id
from platformforge.core.redaction import redact_obj


def _load(p: str | Path) -> dict[str, Any]:
    return json.loads(Path(p).read_text())


def analyze_plan(path: str | Path) -> dict[str, Any]:
    """`terraform show -json plan` → facts. Replace/destroy are flagged for
    rules; the analyzer itself never judges."""
    doc = _load(path)
    facts: list[dict[str, Any]] = []
    for rc in doc.get("resource_changes", []) or []:
        actions = rc.get("change", {}).get("actions", [])
        address = rc.get("address", "")
        facts.append({
            "fact_id": stable_id("PF-IAC", "iac.plan_change", address,
                                 ",".join(actions)),
            "kind": "iac.plan_change", "source": str(path), "tier": 2,
            "location": address,
            "attrs": {
                "address": address, "type": rc.get("type"),
                "name": rc.get("name"), "actions": actions,
                "create": "create" in actions, "delete": "delete" in actions,
                "update": "update" in actions,
                "replace": "delete" in actions and "create" in actions,
                "no_op": actions == ["no-op"],
                "before_sensitive": bool(
                    rc.get("change", {}).get("before_sensitive")),
                "after_sensitive": bool(
                    rc.get("change", {}).get("after_sensitive")),
            }})
    # output changes
    for name, oc in (doc.get("output_changes") or {}).items():
        facts.append({
            "fact_id": stable_id("PF-IAC", "iac.output_change", name),
            "kind": "iac.output_change", "source": str(path), "tier": 2,
            "location": name,
            "attrs": {"name": name,
                      "actions": oc.get("actions", []),
                      "sensitive": bool(oc.get("after_sensitive"))}})
    return {"facts": facts, "counts": {"facts": len(facts)},
            "versions": {"terraform": doc.get("terraform_version"),
                         "format": doc.get("format_version")}}


def analyze_state(path: str | Path) -> dict[str, Any]:
    """`terraform show -json` on state or a raw tfstate → observed facts."""
    doc = _load(path)
    facts: list[dict[str, Any]] = []
    resources = doc.get("values", {}).get("root_module", {}).get("resources") \
        or doc.get("resources") or []
    stack = list(resources)
    while stack:
        r = stack.pop()
        for m in r.get("child_modules", []) or []:
            stack.extend(m.get("resources", []))
        address = r.get("address")
        if not address:
            continue
        inst = (r.get("instances") or [{}])[0]
        values = inst.get("attributes", inst.get("attributes_flat", {})) or {}
        facts.append({
            "fact_id": stable_id("PF-IAC", "iac.state_resource", address),
            "kind": "iac.state_resource", "source": str(path), "tier": 1,
            "location": address,
            "attrs": {"address": address, "type": r.get("type"),
                      "name": r.get("name"),
                      "provider": r.get("provider_name"),
                      "values": redact_obj(values),
                      "graph": {"nodes": [{"kind": "terraform_resource",
                                           "label": address,
                                           "attrs": {"type": r.get("type"),
                                                     "state": True}}]}}})
    return {"facts": facts, "counts": {"facts": len(facts)}}
