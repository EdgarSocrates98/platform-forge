"""§94 Unit economics — cost/request, cost/user, … — only with a real,
measured denominator. Missing or zero denominators produce `unresolved`,
never an interpolated number.
"""

from __future__ import annotations

from typing import Any

DENOMINATORS = ("request", "transaction", "user", "tenant", "service",
                "workload", "environment")


def unit_economics(cost_facts: list[dict[str, Any]],
                   denominators: dict[str, float]) -> dict[str, Any]:
    """cost_facts: rows with `amount` + optional labels for split.
    denominators: {unit: measured_count} — must be measured, >0."""
    total = sum(float(f.get("attrs", {}).get("amount") or
                    f.get("amount") or 0) for f in cost_facts)
    out = {}
    for unit in DENOMINATORS:
        d = denominators.get(unit)
        if d is None or d <= 0:
            out[unit] = {"status": "unresolved",
                         "reason": f"no measured denominator for '{unit}'",
                         "cost_per": None}
            continue
        out[unit] = {"status": "measured", "denominator": d,
                     "cost_per": round(total / d, 6)}
    return {"total_cost": round(total, 4), "unit_economics": out,
            "measured": [u for u, v in out.items()
                         if v["status"] == "measured"],
            "unresolved": [u for u, v in out.items()
                           if v["status"] == "unresolved"],
            "note": "denominators are caller-supplied measurements; "
                    "a zero/missing one stays unresolved"}
