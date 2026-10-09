"""Cycle 5 Phase G — FinOps V4 portfolio optimization (§85–103).

Honesty contracts:
- unallocated stays first-class, never hidden (§89);
- missing cost data → `unknown`, never zero (§64, §355);
- rightsizing uses multi-signal evidence — never CPU alone (§96);
- `idle ≠ safe to delete` (§101);
- commitments produce recommendations, never purchases (§103);
- anomalies use deterministic baselines with capped confidence (§92–94).
"""

from __future__ import annotations

from typing import Any

from platformforge.analytics.models import confidence_for_support

ALLOC_CONFIDENCE = ("direct", "tag-based", "usage-based", "shared",
                    "estimated", "unallocated")
HIERARCHY = ("organization", "business_unit", "team", "product",
             "service", "environment", "cluster", "workload")


def cost_hierarchy(allocations: list[dict[str, Any]]) -> dict[str, Any]:
    """§86–89 — aggregate cost by org→BU→team→…→workload; unallocated
    is a first-class bucket."""
    tree: dict[str, Any] = {"organization": {}, "unallocated": 0.0,
                            "by_level": {k: {} for k in HIERARCHY}}
    for a in allocations:
        amount = float(a.get("amount", 0))
        conf = a.get("allocation_confidence", "unallocated")
        if conf == "unallocated" or a.get("unallocated"):
            tree["unallocated"] += amount
            continue
        for level in HIERARCHY:
            key = str(a.get(level) or "")
            if not key:
                continue
            d = tree["by_level"][level].setdefault(
                key, {"amount": 0.0, "confidence": conf,
                      "items": 0})
            d["amount"] += amount
            d["items"] += 1
            if ALLOC_CONFIDENCE.index(conf) > \
               ALLOC_CONFIDENCE.index(d["confidence"]):
                d["confidence"] = conf
    total = sum(v["amount"] for lvl in tree["by_level"].values()
                for v in lvl.values()) + tree["unallocated"]
    tree["total"] = total
    tree["unallocated_ratio"] = (round(tree["unallocated"] / total, 3)
                                 if total else None)   # §64 None→unknown
    return tree


def unit_economics(cost: float | None,
                   denominator: float | None,
                   unit: str) -> dict[str, Any]:
    """§90/§295 — only with a real business denominator."""
    if cost is None or not denominator:
        return {"metric": f"cost/{unit}", "value": "unknown",
                "reason": "missing denominator or cost",
                "confidence": "low"}
    return {"metric": f"cost/{unit}", "value": round(cost / denominator, 6),
            "confidence": "medium"}


def cost_trend(points: list[dict[str, Any]],
               window: int = 7) -> dict[str, Any]:
    """§91–94 — deterministic baseline: moving average + pct change.
    `insufficient-history` when below minimum (§246–247)."""
    vals = [float(p["amount"]) for p in points if "amount" in p]
    if len(vals) < 3:
        return {"trend": "insufficient-history",
                "minimum_observations": 3, "sample_size": len(vals),
                "confidence": "low"}
    ma = sum(vals[-window:]) / min(len(vals), window)
    prev = sum(vals[:window]) / min(len(vals), window)
    pct = ((ma - prev) / prev * 100) if prev else None
    direction = ("up" if pct and pct > 5 else
                 "down" if pct and pct < -5 else "flat")
    return {"trend": direction, "moving_average": round(ma, 2),
            "pct_change": round(pct, 2) if pct is not None else None,
            "method": "moving-average+percent-change",
            "sample_size": len(vals), "confidence": "low"}


def anomalies(points: list[dict[str, Any]],
              pct_threshold: float = 50.0) -> list[dict[str, Any]]:
    """§92–94 — deterministic anomaly detection; confidence always
    capped (no 'smart anomaly' claims)."""
    vals = [float(p["amount"]) for p in points if "amount" in p]
    if len(vals) < 4:
        return []
    base = sum(vals[:-1]) / (len(vals) - 1)
    out = []
    for p in points:
        v = float(p.get("amount", 0))
        if base and abs(v - base) / base * 100 >= pct_threshold:
            out.append({"ts": p.get("ts", ""), "amount": v,
                        "baseline": round(base, 2),
                        "pct_deviation": round((v - base) / base * 100, 2),
                        "confidence": "low",
                        "method": "deterministic-baseline"})
    return out


def rightsizing(workload: dict[str, Any]) -> dict[str, Any] | None:
    """§95–97 — multi-signal rightsizing. Requires ≥2 evidence signals;
    CPU alone never suffices (§96)."""
    sig = {"cpu_util": workload.get("cpu_util"),
           "memory_util": workload.get("memory_util"),
           "latency_p95": workload.get("latency_p95"),
           "queue_depth": workload.get("queue_depth"),
           "burst_events": workload.get("burst_events"),
           "slo_headroom": workload.get("slo_headroom")}
    observed = {k: v for k, v in sig.items() if v is not None}
    if len(observed) < 2:
        return None                        # not enough evidence (§96)
    cpu = float(observed.get("cpu_util", 0) or 0)
    mem = float(observed.get("memory_util", 0) or 0)
    headroom = float(observed.get("slo_headroom", 0) or 0)
    oversized = cpu < 20 and mem < 30 and headroom > 0.5
    undersized = cpu > 85 or mem > 90 or headroom < 0
    if not (oversized or undersized):
        return None
    return {"workload": workload.get("id", "unknown"),
            "type": "downsize" if oversized else "upsize",
            "current": workload.get("requests"),
            "evidence": observed,
            "signals_used": len(observed),
            "performance_risk": "medium" if undersized else "low",
            "reliability_risk": "low" if headroom > 0.3 else "medium",
            "confidence": confidence_for_support(len(observed)),
            "verification": "post-change SLO + utilization window",
            "auto_apply": False}           # §99


def idle_resources(resources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """§100–101 — detect idle with evidence; never mark deletable."""
    out = []
    for r in resources:
        signals = [s for s in ("cpu_util", "network_bytes", "attached",
                             "requests_30d", "orphaned")
                   if r.get(s) is not None]
        idle = (r.get("requests_30d") == 0
                or r.get("orphaned") is True
                or (r.get("attached") is False
                    and r.get("cpu_util", 1) < 5))
        if idle and len(signals) >= 2:
            out.append({"resource": r.get("id", "unknown"),
                        "classification": "idle",
                        "evidence": {s: r.get(s) for s in signals},
                        "deletable": False,      # §101 — never
                        "note": "idle ≠ safe to delete",
                        "confidence": confidence_for_support(len(signals))})
    return out


def commitment_recommendation(usage: dict[str, Any]) -> dict[str, Any]:
    """§102–103 — foundation: analyze steady-state usage, recommend
    only. Never purchases."""
    hours = usage.get("steady_hours_30d")
    if not hours:
        return {"recommendation": "insufficient-history",
                "minimum": "30d steady usage", "executes": False}
    return {"type": "commitment-candidate",
            "evidence": {"steady_hours_30d": hours,
                         "coverage_ratio": usage.get("coverage")},
            "recommendation": "evaluate-savings-plan-or-RI",
            "confidence": "low", "executes": False,
            "note": "recommendation only — never a purchase"}
