"""Cycle 5 Phase D — platform measurement (§58–71, §252–256).

Diagnostic, never a marketing score (§66, §253). Every dimension shows
observed/declared evidence + gaps + confidence (§67); `unknown` stays
visible (§255); no single collapsed number (§253).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from platformforge.analytics.models import AnalyticsDataQuality, PlatformMetric

MATURITY_DIMENSIONS = ("investment", "adoption", "interfaces",
                       "operations", "measurement")
VALUE_DIMENSIONS = ("adoption", "self-service", "reliability",
                    "delivery", "cost-efficiency", "security",
                    "operational-toil", "developer-experience",
                    "standardization", "policy-compliance")
SCORECARD_LEVELS = ("strong", "moderate", "partial", "at-risk",
                    "unknown")


@dataclass
class MaturityDimension:
    """§67 — one diagnostic axis."""
    name: str
    level: str = "unknown"             # initial|managed|defined|measured|optimizing
    observed_evidence: list[str] = field(default_factory=list)
    declared_evidence: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    confidence: str = "low"

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "level": self.level,
                "observed_evidence": self.observed_evidence,
                "declared_evidence": self.declared_evidence,
                "gaps": self.gaps, "confidence": self.confidence}


def maturity_assessment(signals: dict[str, dict[str, Any]],
                        dq: AnalyticsDataQuality | None = None
                        ) -> dict[str, Any]:
    """§65–67 — maturity V3. `signals`: per-dimension dicts of observed
    facts (each signal lists the capability IDs it observed). Missing
    dimensions report `unknown`, never zero."""
    cap = (dq or AnalyticsDataQuality(sample_size=3,
                                     coverage=1.0,
                                     completeness=1.0)).confidence_cap
    dims = []
    for name in MATURITY_DIMENSIONS:
        sig = signals.get(name)
        if not sig:
            dims.append(MaturityDimension(
                name=name, gaps=[f"no {name} evidence collected"]))
            continue
        obs = sig.get("observed", [])
        dec = sig.get("declared", [])
        score = len(obs) + len(dec)
        level = ("optimizing" if score >= 8 else
                 "measured" if score >= 5 else
                 "defined" if score >= 3 else
                 "managed" if score >= 1 else "initial")
        dims.append(MaturityDimension(
            name=name, level=level, observed_evidence=list(obs),
            declared_evidence=list(dec),
            gaps=list(sig.get("gaps", [])),
            confidence=cap if score >= 3 else "low"))
    return {"schema": "platformforge/maturity/v3",
            "dimensions": [d.to_dict() for d in dims],
            "unknown_dimensions": [d.name for d in dims
                                   if d.level == "unknown"],
            "note": "diagnostic dimensions — not a marketing score"}


def self_service_ratio(successful: int | None,
                       eligible: int | None) -> PlatformMetric:
    """§68 — only when the denominator is observable."""
    m = PlatformMetric(metric_id="platform.self-service-ratio",
                       dimension="self-service",
                       scope={"level": "platform"},
                       unit="ratio", source="golden_path_requests")
    if not eligible:
        m.value = None                # §64 — unknown, not zero
        m.confidence = "low"
        m.evidence = ["denominator not observable"]
        return m
    m.value = round((successful or 0) / eligible, 3)
    m.completeness = 1.0
    m.confidence = "medium" if eligible >= 10 else "low"
    return m


def toil_metrics(events: list[dict[str, Any]]) -> list[PlatformMetric]:
    """§69 — platform-team toil: manual interventions, owner approvals,
    failed self-service, repeated incidents."""
    def _m(mid, val, ev):
        return PlatformMetric(metric_id=mid, dimension="operational-toil",
                              scope={"level": "platform"}, value=val,
                              unit="count", source="history",
                              evidence=ev,
                              confidence="medium" if val else "low")
    manual = [e for e in events if e.get("type") == "manual-intervention"]
    approvals = [e for e in events
                 if e.get("type") == "approval-required"]
    failed_ss = [e for e in events
                 if e.get("type") == "self-service-failed"]
    return [_m("platform.toil.manual-interventions", len(manual),
               [str(e.get("ref", "")) for e in manual[:20]]),
            _m("platform.toil.owner-approvals", len(approvals),
               [str(e.get("ref", "")) for e in approvals[:20]]),
            _m("platform.toil.failed-self-service", len(failed_ss),
               [str(e.get("ref", "")) for e in failed_ss[:20]])]


def time_to_provision(requests: list[dict[str, Any]]) -> PlatformMetric:
    """§70 — median request→ready when both timestamps exist."""
    deltas = []
    for r in requests:
        req, ready = r.get("requested_at"), r.get("ready_at")
        if req and ready:
            from platformforge.live.models import parse_ts
            a, b = parse_ts(req), parse_ts(ready)
            if a and b:
                deltas.append((b - a).total_seconds())
    m = PlatformMetric(metric_id="platform.time-to-provision",
                       dimension="delivery", scope={"level": "platform"},
                       unit="seconds", source="golden_path_requests")
    if not deltas:
        m.value = None
        m.confidence = "low"
        return m
    deltas.sort()
    m.value = deltas[len(deltas) // 2]
    m.completeness = len(deltas) / max(len(requests), 1)
    m.confidence = "medium" if len(deltas) >= 5 else "low"
    return m


def scorecard(dimensions: dict[str, str]) -> dict[str, Any]:
    """§252–255 — decomposed dashboard; unknown stays unknown."""
    out = {k: (v if v in SCORECARD_LEVELS else "unknown")
           for k, v in dimensions.items()}
    return {"schema": "platformforge/scorecard/v1",
            "dimensions": out,
            "unknown": [k for k, v in out.items() if v == "unknown"],
            "collapsed_score": None,
            "note": "no single number — read the dimensions"}
