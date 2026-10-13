"""§90 FinOps v2 — rightsizing, idle, shared cost, forecast, anomalies,
commitments, rate/usage optimization. Every insight is evidence-bound:
without the measured signal the output is `unresolved` + what would
unlock it. No savings number is ever asserted without a denominator.
"""

from __future__ import annotations

import statistics
from typing import Any


def _costs(cost_facts: list[dict[str, Any]]) -> list[tuple[str, float, str]]:
    out = []
    for f in cost_facts:
        if f.get("kind") != "finops.cost":
            continue
        a = f.get("attrs", {})
        out.append((a.get("resource", "?"), float(a.get("amount") or 0),
                    a.get("period", "unknown")))
    return out


def idle_resources(cost_facts: list[dict[str, Any]],
                   utilization: dict[str, float] | None = None,
                   idle_threshold: float = 0.02) -> dict[str, Any]:
    """Cost-bearing resources with measured utilization below threshold.
    Without utilization per resource the whole dimension is unresolved —
    cost alone never proves idle."""
    res = _costs(cost_facts)
    if utilization is None:
        return {"status": "unresolved",
                "reason": "no utilization measurements supplied",
                "unlock": "supply {resource: cpu/mem/utilization} measured "
                          "over the billing window"}
    idle = [{"resource": r, "cost": c, "utilization": utilization[r]}
            for r, c, _ in res
            if r in utilization and utilization[r] <= idle_threshold]
    return {"status": "measured", "idle": sorted(idle,
            key=lambda x: -x["cost"]),
            "idle_cost_total": round(sum(i["cost"] for i in idle), 4),
            "threshold": idle_threshold,
            "resources_without_util": sorted(
                {r for r, _, _ in res} - set(utilization))}


def rightsizing(cost_facts: list[dict[str, Any]],
                requested_vs_used: dict[str, dict[str, float]]
                | None = None) -> dict[str, Any]:
    """Resources where requested ≫ used. Needs measured request+usage —
    without it the output is unresolved, never a guessed percentage."""
    if not requested_vs_used:
        return {"status": "unresolved",
                "reason": "no requested-vs-used measurements supplied",
                "unlock": "supply {resource: {requested: x, used: y}}"}
    over = []
    for r, m in requested_vs_used.items():
        req, used = float(m.get("requested") or 0), float(m.get("used") or 0)
        if req > 0 and used / req < 0.5:
            over.append({"resource": r, "requested": req, "used": used,
                         "headroom_ratio": round(1 - used / req, 3)})
    cost_by_res = {r: c for r, c, _ in _costs(cost_facts)}
    return {"status": "measured",
            "oversized": sorted(over, key=lambda x: -cost_by_res.get(
                x["resource"], 0)),
            "note": "headroom is capacity signal; savings require the "
                    "billed rate for the smaller shape — not asserted"}


def anomalies(cost_facts: list[dict[str, Any]],
              min_periods: int = 3,
              z_threshold: float = 2.0) -> dict[str, Any]:
    """Period-over-period anomalies per resource: |z| on the cost series.
    Needs ≥ min_periods to compare; fewer → unresolved."""
    series: dict[str, list[tuple[str, float]]] = {}
    for r, c, p in _costs(cost_facts):
        series.setdefault(r, []).append((p, c))
    out, under_reported = [], []
    for r, pts in sorted(series.items()):
        pts.sort()
        if len(pts) < min_periods:
            under_reported.append(r)
            continue
        vals = [v for _, v in pts]
        base, test = vals[:-1], vals[-1]
        if len(base) < 2 or not statistics.stdev(base):
            continue
        z = (test - statistics.mean(base)) / statistics.stdev(base)
        if abs(z) >= z_threshold:
            out.append({"resource": r, "latest_period": pts[-1][0],
                        "latest": test, "baseline_mean":
                        round(statistics.mean(base), 4),
                        "z": round(z, 2)})
    return {"status": "measured" if out or not under_reported
            else "partial",
            "anomalies": out,
            "series_too_short": under_reported,
            "method": "z-score on own-period series, ≥3 periods",
            "note": "anomaly = statistical outlier, not a cause"}


def forecast(cost_facts: list[dict[str, Any]],
             min_periods: int = 3) -> dict[str, Any]:
    """Linear trend over period totals — labeled estimate, never a
    commitment. Fewer periods → unresolved."""
    totals: dict[str, float] = {}
    for _, c, p in _costs(cost_facts):
        totals[p] = totals.get(p, 0) + c
    periods = sorted(totals)
    if len(periods) < min_periods:
        return {"status": "unresolved",
                "reason": f"need ≥{min_periods} periods, have "
                          f"{len(periods)}",
                "periods": periods}
    xs = list(range(len(periods)))
    ys = [totals[p] for p in periods]
    xm, ym = statistics.mean(xs), statistics.mean(ys)
    var = sum((x - xm) ** 2 for x in xs) or 1
    slope = sum((x - xm) * (y - ym) for x, y in zip(xs, ys)) / var
    nxt = ym + slope * (len(periods) - xm)
    return {"status": "measured",
            "periods": {p: round(totals[p], 4) for p in periods},
            "next_period_estimate": round(max(0.0, nxt), 4),
            "slope": round(slope, 4),
            "method": "OLS over period totals",
            "note": "estimate only — seasonality and commitments are "
                    "not modeled"}


def commitments(cost_facts: list[dict[str, Any]],
                committed: dict[str, float] | None = None) -> dict[str, Any]:
    """RI/SP/CUD coverage: committed spend vs on-demand. Without declared
    commitments → unresolved (a zero guess would be fabrication)."""
    total = round(sum(c for _, c, _ in _costs(cost_facts)), 4)
    if committed is None:
        return {"status": "unresolved", "total_cost": total,
                "reason": "no commitment instruments declared",
                "unlock": "supply {resource|service: committed_amount}"}
    covered = round(sum(committed.values()), 4)
    return {"status": "measured", "total_cost": total,
            "committed": covered,
            "coverage_ratio": round(covered / total, 4) if total else None,
            "on_demand_residual": round(max(0.0, total - covered), 4)}


def shared_cost(cost_facts: list[dict[str, Any]],
                split: dict[str, Any] | None = None) -> dict[str, Any]:
    """Shared-cost allocation: untagged/shared resources distributed by
    declared policy. No declared split → listed, never silently spread."""
    untagged = [{"resource": r, "cost": c}
                for r, c, _ in _costs(cost_facts)
                if not _tags_for(cost_facts, r)]
    if split is None:
        return {"status": "measured", "shared_unallocated": untagged,
                "shared_cost_total": round(sum(u["cost"]
                                               for u in untagged), 4),
                "distributed": None,
                "reason": "no split policy declared — amounts listed, "
                          "not distributed",
                "unlock": "supply {split: {tenant: weight}}"}
    total_w = sum(split.values()) or 1
    dist = {}
    for u in untagged:
        for tenant, w in split.items():
            dist[tenant] = round(dist.get(tenant, 0) +
                                 u["cost"] * w / total_w, 4)
    return {"status": "measured", "shared_unallocated": untagged,
            "distributed": dist, "policy": split}


def _tags_for(cost_facts: list[dict[str, Any]], res: str) -> dict:
    for f in cost_facts:
        if f.get("kind") == "finops.cost" and \
                f.get("attrs", {}).get("resource") == res:
            return f["attrs"].get("tags") or {}
    return {}


def finops_report(cost_facts: list[dict[str, Any]],
                  utilization: dict[str, float] | None = None,
                  requested_vs_used: dict[str, dict[str, float]] | None
                  = None,
                  committed: dict[str, float] | None = None,
                  split: dict[str, Any] | None = None) -> dict[str, Any]:
    """§90 composite — every dimension independently measured/unresolved."""
    return {"idle": idle_resources(cost_facts, utilization),
            "rightsizing": rightsizing(cost_facts, requested_vs_used),
            "anomalies": anomalies(cost_facts),
            "forecast": forecast(cost_facts),
            "commitments": commitments(cost_facts, committed),
            "shared": shared_cost(cost_facts, split),
            "note": "each dimension is independently evidence-bound; "
                    "unresolved ≠ zero"}
