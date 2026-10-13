"""FeatureException — the only door for new capability during freeze
(§6). A request that cannot prove a real-world blocker is refused."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

REQUIRED = (
    "id", "requested_capability", "reason", "real_world_blocker",
    "existing_capability_insufficient", "alternatives_considered",
    "architectural_impact", "schema_impact", "agent_impact",
    "operations_impact", "decision",
)
DECISIONS = ("approved", "rejected", "deferred")


@dataclass(frozen=True)
class FeatureException:
    id: str = ""
    requested_capability: str = ""
    reason: str = ""
    real_world_blocker: str = ""
    existing_capability_insufficient: str = ""
    alternatives_considered: tuple[str, ...] = ()
    architectural_impact: str = "none"
    schema_impact: str = "none"
    agent_impact: str = "none"
    operations_impact: str = "none"
    decision: str = "rejected"
    decided_by: str = ""
    evidence: tuple[str, ...] = ()
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = {k: getattr(self, k) for k in REQUIRED}
        d["alternatives_considered"] = list(self.alternatives_considered)
        d["decided_by"] = self.decided_by
        d["evidence"] = list(self.evidence)
        d["schema"] = "platformforge/feature-exception/v1"
        return d


def exception_errors(d: dict[str, Any]) -> list[str]:
    """§6 — every field required; decision must be in the closed set;
    approval requires a named real_world_blocker + evidence."""
    errs = [f"missing field: {k}" for k in REQUIRED if not d.get(k)]
    if d.get("decision") and d["decision"] not in DECISIONS:
        errs.append(f"decision {d['decision']!r} not in {DECISIONS}")
    if d.get("decision") == "approved":
        if not d.get("real_world_blocker"):
            errs.append("approved exception without real_world_blocker")
        if not d.get("evidence"):
            errs.append("approved exception without evidence")
        if d.get("architectural_impact") in ("", "unknown"):
            errs.append("approved exception with unassessed architectural_impact")
    return errs
