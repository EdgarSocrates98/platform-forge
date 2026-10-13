"""Cycle 5 Phase I — OptimizationEngine (§202–212).

Priority is decomposed (§206–208): impact / confidence / effort /
risk / scope / freshness — never a black-box score. `plan()` converts
a recommendation to a ChangeIntent — the *only* path toward action
(§210–211, §303): policy, approval, envelope, verification all still
apply in the Cycle 4 pipeline.
"""

from __future__ import annotations

from typing import Any

from platformforge.analytics.models import AnalyticsDataQuality
from platformforge.optimize.models import OptimizationOpportunity, OptimizationRecommendation

IMPACT_ORDER = {"high": 3, "medium": 2, "low": 1}
CONF_ORDER = {"high": 3, "medium": 2, "low": 1}
EFFORT_ORDER = {"low": 3, "medium": 2, "high": 1, "unknown": 0}


def priority_of(rec: OptimizationRecommendation) -> dict[str, Any]:
    """§206–208 — decomposed priority; the tuple IS the output."""
    impact = "high" if (rec.estimated_savings or 0) >= 1000 or \
        rec.type in ("security", "reliability") else \
        "medium" if (rec.estimated_savings or 0) >= 100 else "low"
    freshness = "fresh"
    dims = {"impact": impact, "confidence": rec.confidence,
            "effort": rec.effort, "risk": rec.reliability_risk,
            "scope": rec.scope, "evidence_freshness": freshness}
    rank = (IMPACT_ORDER[impact] * 3 + CONF_ORDER[rec.confidence] * 3 +
            EFFORT_ORDER.get(rec.effort, 0) * 2 +
            (0 if rec.reliability_risk in ("low",) else -2) +
            (1 if freshness == "fresh" else -1))
    dims["rank_score"] = rank
    dims["note"] = "decomposed dimensions — not a black-box score"
    return dims


class OptimizationEngine:
    """Deterministic scan over analytics outputs → opportunities →
    recommendations → ChangeIntents. Never touches transports (§211)."""

    def __init__(self, dq: AnalyticsDataQuality | None = None):
        self.dq = dq or AnalyticsDataQuality()
        self._opportunities: list[OptimizationOpportunity] = []
        self._recommendations: list[OptimizationRecommendation] = []

    def add_opportunity(self, opp: OptimizationOpportunity) -> None:
        self._opportunities.append(opp)

    def opportunities(self) -> list[OptimizationOpportunity]:
        return list(self._opportunities)

    def recommendations(self) -> list[OptimizationRecommendation]:
        """§294 — only promotable opportunities become recs."""
        out = []
        cap = self.dq.confidence_cap            # §251
        for i, o in enumerate(self._opportunities):
            if not o.promotable():
                continue
            conf = {"high": "high", "medium": "medium"}.get(
                cap, "low")
            if o.uncertainty == "medium" and conf == "high":
                conf = "medium"
            rec = OptimizationRecommendation(
                recommendation_id=f"opt-{i}-{o.opportunity_id}",
                type=o.type, scope=o.scope,
                estimated_savings=o.estimated_savings,
                savings_unit=o.savings_unit,
                confidence=conf, evidence=list(o.evidence),
                effort="unknown",
                effort_rationale="not estimated — declare explicitly",
                verification="post-change verification via ops pipeline")
            rec.priority = priority_of(rec)
            out.append(rec)
        out.sort(key=lambda r: -r.priority.get("rank_score", 0))
        self._recommendations = out
        return out

    def portfolio(self, top: int = 10) -> dict[str, Any]:
        """§212 — top-N with dimensions visible."""
        recs = self.recommendations()
        return {"schema": "platformforge/optimization-portfolio/v1",
                "total_opportunities": len(self._opportunities),
                "promoted": len(recs),
                "suppressed": len(self._opportunities) - len(recs),
                "data_quality": self.dq.to_dict(),
                "top": [{**r.to_dict()} for r in recs[:top]]}

    @staticmethod
    def plan(rec: OptimizationRecommendation):
        """§261/§303 — recommendation → ChangeIntent. The ONLY bridge;
        no path exists from here to ExecutionEnvelope directly."""
        from platformforge.ops.models import ChangeIntent, Reason
        return ChangeIntent(
            intent_id=f"opt-{rec.recommendation_id}",
            reason=Reason(type="recommendation",
                          recommendation_ids=[rec.recommendation_id],
                          detail=f"{rec.type} optimization "
                                 f"{rec.recommendation_id}"),
            target_resources=sorted(set(rec.scope.values())),
            desired_change={"optimization": rec.type,
                            "proposed": rec.proposed,
                            "recommendation_id": rec.recommendation_id},
            risk_context={"confidence": rec.confidence,
                          "performance_risk": rec.performance_risk,
                          "reliability_risk": rec.reliability_risk},
            expected_outcome=rec.verification)
