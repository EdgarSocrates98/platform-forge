"""Capacity — utilization facts in, saturation classes out. No
interpolation: a fact reports what was measured, a rule applies the
threshold."""

from __future__ import annotations

from typing import Any


def classify(utilization: float | None) -> str:
    if utilization is None:
        return "unresolved"
    if utilization >= 0.95:
        return "saturated"
    if utilization >= 0.85:
        return "hot"
    if utilization >= 0.60:
        return "warm"
    return "cool"


def capacity(items: list[dict[str, Any]]) -> dict[str, Any]:
    """items: [{resource, used, limit, unit?}] — limit=None → unresolved."""
    out = []
    for it in items:
        used, limit = it.get("used"), it.get("limit")
        util = None
        if isinstance(used, (int, float)) and isinstance(limit, (int, float)) \
                and limit > 0:
            util = used / limit
        out.append({"resource": it.get("resource"), "used": used,
                    "limit": limit, "unit": it.get("unit"),
                    "utilization": round(util, 4) if util is not None else None,
                    "class": classify(util)})
    hot = [o["resource"] for o in out if o["class"] in ("hot", "saturated")]
    unresolved = [o["resource"] for o in out if o["class"] == "unresolved"]
    return {"capacity": out, "hot": hot, "unresolved_resources": unresolved,
            "counts": {"items": len(out), "hot": len(hot),
                       "unresolved": len(unresolved)}}
