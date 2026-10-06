"""FOCUS-shaped output — map internal cost records to FOCUS-ish columns.
Prep/normalization layer, not a full FOCUS engine; unmapped fields are
reported, not invented."""

from __future__ import annotations

from typing import Any

FOCUS_MAP = {
    "resource": "ResourceId", "amount": "BilledCost", "currency": "Currency",
    "period": "BillingPeriod", "service": "ServiceName",
    "unit": "PricingUnit", "region": "RegionId", "account": "BillingAccountId",
}


def to_focus(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out_rows, unmapped = [], set()
    for r in rows:
        row = {FOCUS_MAP.get(k, k): v for k, v in r.items()}
        for k in r:
            if k not in FOCUS_MAP:
                unmapped.add(k)
        row.setdefault("ChargeCategory", "usage")
        out_rows.append(row)
    return {"focus_rows": out_rows, "unmapped_fields": sorted(unmapped),
            "spec": "FOCUS-like projection; validate against the ratified "
                    "FOCUS version before external use",
            "counts": {"rows": len(out_rows)}}
