"""Cycle 5 Phase I — optimization contracts (§97–98, §204–210).

Pipeline (§210): Evidence → Pattern → Opportunity → Recommendation →
ChangeIntent → Cycle 4. The engine NEVER produces an
ExecutionEnvelope and NEVER executes (§211, §303).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

OPT_TYPES = ("cost", "capacity", "reliability", "security",
             "platform-product", "operational", "standardization")
EFFORTS = ("low", "medium", "high", "unknown")


@dataclass
class OptimizationOpportunity:
    """§209 — a detected improvement signal, before recommendation."""
    opportunity_id: str
    type: str                          # OPT_TYPES
    scope: dict[str, str]
    evidence: list[str] = field(default_factory=list)
    pattern_refs: list[str] = field(default_factory=list)
    estimated_savings: float | None = None
    savings_unit: str = ""
    uncertainty: str = "high"          # low|medium|high
    coverage: float | None = None
    freshness: str = "unknown"

    def promotable(self) -> bool:
        """§294/§303 — high uncertainty or thin coverage never
        auto-promotes to a recommendation."""
        if self.uncertainty == "high":
            return False
        if self.coverage is not None and self.coverage < 0.5:
            return False
        return bool(self.evidence)

    def to_dict(self) -> dict[str, Any]:
        return {"schema": "platformforge/optimization-opportunity/v1",
                **asdict(self)}


@dataclass
class OptimizationRecommendation:
    """§97–98 — the governed output object."""
    recommendation_id: str
    type: str
    scope: dict[str, str]
    current: dict[str, Any] = field(default_factory=dict)
    proposed: dict[str, Any] = field(default_factory=dict)
    estimated_savings: float | None = None
    savings_unit: str = ""
    performance_risk: str = "unknown"
    reliability_risk: str = "unknown"
    confidence: str = "low"
    evidence: list[str] = field(default_factory=list)
    verification: str = ""
    effort: str = "unknown"            # §208
    effort_rationale: str = ""
    priority: dict[str, Any] = field(default_factory=dict)
    auto_apply: bool = False           # §99 — never

    def to_dict(self) -> dict[str, Any]:
        return {"schema": "platformforge/optimization-recommendation/v1",
                **asdict(self), "executes": False}
