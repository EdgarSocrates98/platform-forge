"""BudgetReconciliation (§81–88) — planned vs observed, per axis.

Observed absent → `unresolved` (§85), never a fake zero. Savings claims
require observed usage + declared pricing — "saved $X" without both is
refused (§86, §293 north star). Historical mismatch feeds routing signal
(§88) as data, never self-modifying policy (§153).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

SCHEMA = "platformforge/reconciliation/v1"

AXES = ("tokens", "context", "tools", "agents", "provider_calls",
        "duration", "money")


@dataclass
class AxisRecon:
    planned: float | None
    observed: float | None
    state: str              # ok|over|under|unresolved
    error_pct: float | None = None   # §84 calibration error

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BudgetReconciliation:
    schema: str = SCHEMA
    run_id: str = ""
    axes: dict[str, AxisRecon] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"schema": self.schema, "run_id": self.run_id,
                "axes": {k: v.to_dict() for k, v in self.axes.items()},
                "calibrated_axes": [k for k, v in self.axes.items()
                                    if v.state != "unresolved"],
                "unresolved_axes": [k for k, v in self.axes.items()
                                    if v.state == "unresolved"]}


def reconcile(planned: dict[str, float | None],
              observed: dict[str, float | None],
              run_id: str = "", *,
              tolerance_pct: float = 20.0) -> BudgetReconciliation:
    """§82–87 — per-axis compare. `observed=None` means the axis was not
    measured → unresolved, never treated as 0."""
    rec = BudgetReconciliation(run_id=run_id)
    for axis in AXES:
        p = planned.get(axis)
        o = observed.get(axis)
        if p is None and o is None:
            continue
        if o is None:
            rec.axes[axis] = AxisRecon(p, None, "unresolved")
            continue
        if p is None:
            rec.axes[axis] = AxisRecon(None, o, "unresolved")
            continue
        err = ((o - p) / p * 100.0) if p else (100.0 if o else 0.0)
        state = "ok" if abs(err) <= tolerance_pct else \
            ("over" if err > 0 else "under")
        rec.axes[axis] = AxisRecon(p, o, state, round(err, 1))
    return rec


def savings_claim(observed_spend: float | None,
                  declared_pricing: bool) -> dict[str, Any]:
    """§86/§293 — a $-savings claim needs observed spend AND declared
    pricing; otherwise the honest answer is unresolved."""
    if observed_spend is None:
        return {"claim": "unresolved",
                "reason": "no observed usage — cannot claim savings",
                "code": "PF-ECONOMY-USAGE-UNOBSERVED"}
    if not declared_pricing:
        return {"claim": "unresolved",
                "reason": "tokens observed but pricing absent — cost "
                          "unresolved, not $0",
                "code": "PF-ECONOMY-PRICING-MISSING",
                "observed_spend": observed_spend}
    return {"claim": "supported",
            "observed_spend": observed_spend}
