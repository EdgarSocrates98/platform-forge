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

# FOCUS required columns for the Cost and Usage dataset — stable
# across the ratified 1.x line (1.0 → 1.4; presence-only check, dtype
# validation is a host-side concern). FOCUS 1.3/1.4 added new datasets
# (Billing Period, Contract Commitment) — detected, not validated here.
FOCUS_REQUIRED_V1 = {
    "BilledCost", "BillingAccountId", "BillingPeriodStart",
    "BillingPeriodEnd", "ChargeCategory", "ChargeClass",
    "ChargePeriodStart", "ChargePeriodEnd", "Currency",
    "ServiceName", "SkuId",
}

# Versions whose Cost-and-Usage column contract we can honestly check.
# An unknown version must never produce a "compliant" verdict.
FOCUS_KNOWN_VERSIONS = ("1.0", "1.1", "1.2", "1.3", "1.4")

# Dataset column signatures — best-effort detection, not conformance.
_FOCUS_DATASETS = {
    "cost-and-usage": {"BilledCost", "BillingPeriodStart",
                       "ChargeCategory"},
    "billing-period": {"BillingPeriodStatus", "InvoiceIssuerName"},
    "contract-commitment": {"ContractCommitmentId", "ContractId",
                            "ContractCommitmentCost"},
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


def detect_datasets(rows: list[dict[str, Any]]) -> list[str]:
    """Best-effort: which FOCUS datasets do these rows look like?
    Detection ≠ conformance — reported as `detected`, never `compliant`."""
    cols = set().union(*(r.keys() for r in rows)) if rows else set()
    return [name for name, sig in _FOCUS_DATASETS.items()
            if sig <= cols]


def validate_focus(rows: list[dict[str, Any]],
                   spec_version: str = "1.0") -> dict[str, Any]:
    """§93 — explicit compliance verdict, never implied."""
    if spec_version not in FOCUS_KNOWN_VERSIONS:
        return {"focus_compliant": False,
                "refusal": "PF-FINOPS-FOCUS-VERSION",
                "spec_version": spec_version,
                "unlock": "supported versions: "
                          f"{list(FOCUS_KNOWN_VERSIONS)}"}
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
            "datasets_detected": detect_datasets(rows),
            "rows_checked": len(rows),
            "rows_failing": len(missing_per_row),
            "missing_columns": missing_per_row[:10],
            "scope": "Cost and Usage columns only — Billing Period / "
                     "Contract Commitment datasets are detected, not "
                     "conformance-checked",
            "note": ("schema+version validated against FOCUS "
                     f"{spec_version} required columns" if ok else
                     "not FOCUS-compliant — missing required columns; "
                     "fix before claiming compliance")}

