"""Cycle 5 — platform/security debt + portfolio (§129–141).

Debt items are evidence records, never a collapsed score (§137). Age
matters (§136). Nothing is auto-retired (§141) — recommendations only.
Capability health stays decomposable (§84).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

DEBT_TYPES = ("unsupported-version", "manual-path", "missing-ownership",
              "missing-slo", "policy-exception", "unallocated-cost",
              "repeated-drift", "manual-runbook",
              "non-standard-deployment", "security-exposure")


@dataclass
class DebtItem:
    """§134–136."""
    type: str
    scope: dict[str, str]
    evidence: list[str] = field(default_factory=list)
    age_days: int | None = None
    impact: str = "unknown"
    owner: str = ""
    recommended_path: str = ""
    confidence: str = "low"

    def to_dict(self) -> dict[str, Any]:
        return {"schema": "platformforge/debt-item/v1", **asdict(self)}


def debt_portfolio(items: list[DebtItem]) -> dict[str, Any]:
    """Decomposed — never one 'tech debt score' (§137)."""
    by_type: dict[str, int] = {}
    aged = []
    for i in items:
        by_type[i.type] = by_type.get(i.type, 0) + 1
        if i.age_days and i.age_days >= 30:
            aged.append({"type": i.type, "scope": i.scope,
                         "age_days": i.age_days,
                         "evidence": i.evidence})
    aged.sort(key=lambda a: -a["age_days"])
    return {"schema": "platformforge/debt-portfolio/v1",
            "total_items": len(items), "by_type": by_type,
            "aged_30d_plus": aged,
            "collapsed_score": None,
            "note": "decomposed items — read dimensions, not a score"}


def capability_health(cap: str, signals: dict[str, Any]) -> dict[str, Any]:
    """§82–84 — capability dimensions, decomposable."""
    dims = {"availability": signals.get("availability"),
            "success_rate": signals.get("success_rate"),
            "latency": signals.get("latency"),
            "cost": signals.get("cost"),
            "adoption": signals.get("adoption"),
            "policy_friction": signals.get("policy_friction"),
            "support_burden": signals.get("support_burden")}
    return {"schema": "platformforge/capability-health/v1",
            "capability": cap,
            "dimensions": {k: (v if v is not None else "unknown")
                           for k, v in dims.items()},
            "aggregate": None,
            "note": "decomposable — no opaque score"}


def portfolio_quadrant(capabilities: dict[str, dict[str, Any]]
                       ) -> dict[str, Any]:
    """§138–141 — value-vs-cost quadrant; recommendations only."""
    out = {"high_adoption_low_support": [], "high_adoption_high_support": [],
           "low_adoption_high_cost": [], "low_adoption_low_cost": [],
           "unclassified": []}
    for cap, s in capabilities.items():
        ad = s.get("adoption")
        sup = s.get("support_burden")
        cost = s.get("cost_monthly")
        if ad is None:
            out["unclassified"].append(cap)
            continue
        high_ad = ad >= 0.5
        high_sup = (sup or 0) >= 3 or (cost or 0) >= 1000
        key = ("high_adoption_high_support" if high_ad and high_sup else
               "high_adoption_low_support" if high_ad else
               "low_adoption_high_cost" if high_sup else
               "low_adoption_low_cost")
        out[key].append(cap)
    out["auto_retire"] = False                # §141
    out["note"] = "quadrant informs review — nothing is retired here"
    return out
