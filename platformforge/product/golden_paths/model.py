"""§74 Golden Path contract — a path is a governed capability, not a
template. The model binds repo+CI+security+artifact+deployment+runtime+
observability+SLO+ownership+cost (§76) and every path documents its
escape hatch (§77): happy path, supported customizations, the escape
route, and what is explicitly unsupported.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

REQUIRED_FIELDS = ("id", "name", "version", "use_case", "inputs",
                   "outputs", "steps", "policies", "ownership",
                   "observability", "security", "cost", "slo",
                   "escape_hatches", "supported_variants")


@dataclass
class GoldenPath:
    id: str
    name: str
    version: str
    use_case: str
    inputs: list[dict[str, Any]] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    steps: list[dict[str, Any]] = field(default_factory=list)
    policies: list[str] = field(default_factory=list)
    ownership: dict[str, Any] = field(default_factory=dict)
    observability: dict[str, Any] = field(default_factory=dict)
    security: dict[str, Any] = field(default_factory=dict)
    cost: dict[str, Any] = field(default_factory=dict)
    slo: dict[str, Any] = field(default_factory=dict)
    escape_hatches: dict[str, Any] = field(default_factory=dict)
    supported_variants: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, doc: dict[str, Any]) -> GoldenPath:
        pid = doc.get("id", "?")
        missing = [f for f in REQUIRED_FIELDS if f not in doc]
        if missing:
            raise ValueError(f"golden path {pid} missing "
                             f"required fields: {missing}")
        # §96 — structural validation, not just presence.
        for i in doc["inputs"]:
            if not isinstance(i, dict) or not i.get("name"):
                raise ValueError(f"golden path {pid}: input without name")
        for s in doc["steps"]:
            if not isinstance(s, dict) or not s.get("id") \
                    or not s.get("produces"):
                raise ValueError(f"golden path {pid}: step without "
                                 "id/produces")
        if not doc["ownership"].get("owner_field"):
            raise ValueError(f"golden path {pid}: ownership lacks "
                             "owner_field")
        for f in ("observability", "security", "cost"):
            if not isinstance(doc[f], dict) or not doc[f]:
                raise ValueError(f"golden path {pid}: {f} must be a "
                                 "non-empty mapping")
        # slo is required as a key but may be {} — infra paths produce no
        # service-level SLO; empty is an honest "not applicable".
        if not isinstance(doc["slo"], dict):
            raise TypeError(f"golden path {pid}: slo must be a mapping")
        for f in ("happy_path", "escape_hatch"):
            if not doc["escape_hatches"].get(f):
                raise ValueError(f"golden path {pid}: escape_hatches "
                                 f"lacks {f}")
        return cls(**{f: doc[f] for f in REQUIRED_FIELDS})

    def capability(self) -> dict[str, Any]:
        """§79 — machine-readable self-service contract. approval_required
        stays True: paths propose changes, they never auto-mutate."""
        return {
            "capability": f"platform.path.{self.id}",
            "version": self.version,
            "use_case": self.use_case,
            "inputs": self.inputs,
            "policy": {"policies": self.policies,
                       "escape_hatches": self.escape_hatches},
            "risk": {"severity": "medium",
                     "boundaries": ["scaffold", "pr"]},
            "approval_required": True,
            "mutates": False,
        }
