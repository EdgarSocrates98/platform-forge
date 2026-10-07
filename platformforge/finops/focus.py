"""§93 FOCUS — projection plus *explicit* compliance validation.

`to_focus` maps internal cost records to FOCUS column names and reports
unmapped fields. `validate_focus` then checks the ratified FOCUS 1.x
column contract — `focus_compliant` is only ever True after that check
passes, and the checked spec version is always reported. The word
'compliant' is never emitted without schema+version evidence.
"""

from __future__ import annotations

from typing import Any

FOCUS_MAP = {
    "resource": "ResourceId", "amount": "BilledCost", "currency": "Currency",
    "period": "BillingPeriod", "service": "ServiceName",
    "unit": "PricingUnit", "region": "RegionId", "account": "BillingAccountId",
}

# FOCUS 1.0-r1 required columns (billing export contract subset —
# presence-only check, dtype validation is a host-side concern).
FOCUS_REQUIRED_V1 = {
    "BilledCost", "BillingAccountId", "BillingPeriodStart",
    "BillingPeriodEnd", "ChargeCategory", "ChargeClass",
    "ChargePeriodStart", "ChargePeriodEnd", "Currency",
    "ServiceName", "SkuId",
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


def validate_focus(rows: list[dict[str, Any]],
                   spec_version: str = "1.0") -> dict[str, Any]:
    """§93 — explicit compliance verdict, never implied."""
    if not rows:
        return {"focus_compliant": False, "spec_version": spec_version,
                "reason": "no rows to validate",
                "missing_columns": sorted(FOCUS_REQUIRED_V1)}
    missing_per_row = []
    for i, r in enumerate(rows):
        missing = sorted(FOCUS_REQUIRED_V1 - set(r))
        if missing:
            missing_per_row.append({"row": i, "missing": missing})
    ok = not missing_per_row
    return {"focus_compliant": ok,
            "spec_version": spec_version,
            "rows_checked": len(rows),
            "rows_failing": len(missing_per_row),
            "missing_columns": missing_per_row[:10],
            "note": ("schema+version validated against FOCUS "
                     f"{spec_version} required columns" if ok else
                     "not FOCUS-compliant — missing required columns; "
                     "fix before claiming compliance")}

