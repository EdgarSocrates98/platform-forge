"""§91 cloud cost ingestion — normalize provider billing exports into
generic cost rows that `cost_facts` consumes.

Recognized formats (detected by column shape, never by filename):
  AWS CUR:          lineItem/ResourceId, lineItem/UnblendedCost, …
  Azure Cost Mgmt:  ResourceId, PreTaxCost / CostInBillingCurrency, …
  GCP Billing:      resource.name / labels, cost + usage.unit, …
  OpenCost:         window/totalCost or per-item totalCost
  Kubecost:         result[].cost / totalCost per resource

Undetected formats produce `unresolved`, never silent skipping.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def _rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix == ".csv":
        return list(csv.DictReader(path.open()))
    doc = json.loads(path.read_text())
    if isinstance(doc, list):
        return doc
    # OpenCost/Kubecost shapes keep rows nested
    for key in ("rows", "data", "results", "result", "items"):
        if isinstance(doc.get(key), list):
            return doc[key]
    return []


def _num(v: Any) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def detect_format(row: dict[str, Any]) -> str | None:
    ks = set(row)
    if any(k.startswith("lineItem/") for k in ks) or \
            "lineItem/UnblendedCost" in ks:
        return "aws_cur"
    if "PreTaxCost" in ks or "CostInBillingCurrency" in ks or \
            "microsoft.costmanagement" in str(row.get("type", "")).lower():
        return "azure_costmgmt"
    if "cost" in ks and ("usage" in ks or "labels" in ks or
                         "sku.description" in ks or "project.id" in ks):
        return "gcp_billing"
    if "totalCost" in ks or ("window" in ks and "totalEfficiency" in ks):
        return "opencost" if "window" in ks else "kubecost"
    return None


def normalize_row(row: dict[str, Any], fmt: str) -> dict[str, Any] | None:
    """Provider row → generic {resource, amount, service, period,
    currency, tags}. Returns None when the amount is unmeasurable."""
    if fmt == "aws_cur":
        amount = _num(row.get("lineItem/UnblendedCost"))
        res = row.get("lineItem/ResourceId") or \
            row.get("lineItem/LineItemDescription")
        return {"resource": str(res), "amount": amount,
                "service": row.get("product/ProductName")
                or row.get("lineItem/ProductCode"),
                "period": row.get("lineItem/BillingPeriodStartDate")
                or row.get("bill/BillingPeriodStartDate"),
                "currency": row.get("lineItem/CurrencyCode"),
                "tags": row.get("resourceTags") or {}} \
            if res and amount is not None else None
    if fmt == "azure_costmgmt":
        amount = _num(row.get("PreTaxCost")) or \
            _num(row.get("CostInBillingCurrency"))
        res = row.get("ResourceId") or row.get("MeterCategory")
        return {"resource": str(res), "amount": amount,
                "service": row.get("ServiceName") or row.get("MeterCategory"),
                "period": row.get("UsageDate") or row.get("BillingPeriod"),
                "currency": row.get("Currency"),
                "tags": row.get("Tags") or {}} \
            if res and amount is not None else None
    if fmt == "gcp_billing":
        amount = _num(row.get("cost"))
        res = row.get("resource.name") or row.get("resource") or \
            row.get("sku.description") or row.get("project.id")
        labels = row.get("labels")
        if isinstance(labels, str):
            labels = dict(kv.split(":", 1) for kv in labels.split(",")
                          if ":" in kv) if labels else {}
        return {"resource": str(res), "amount": amount,
                "service": row.get("service.description")
                or row.get("sku.description"),
                "period": row.get("usage_start_time")
                or row.get("invoice.month"),
                "currency": row.get("currency"),
                "tags": labels or {}} \
            if res and amount is not None else None
    if fmt in ("opencost", "kubecost"):
        amount = _num(row.get("totalCost"))
        props = row.get("properties") if isinstance(
            row.get("properties"), dict) else {}
        res = row.get("name") or row.get("resource") or props.get("name")
        win = row.get("window")
        return {"resource": str(res or "unresolved"),
                "amount": amount,
                "service": props.get("service") or row.get("service"),
                "period": win.get("start") if isinstance(win, dict)
                else win,
                "currency": "USD",
                "tags": props.get("labels") or {}} \
            if amount is not None else None
    return None


def ingest_billing(path: str | Path) -> dict[str, Any]:
    """Detect provider format → normalized rows → cost_facts shape."""
    rows = _rows(Path(path))
    formats: dict[str, int] = {}
    normalized: list[dict[str, Any]] = []
    unrecognized = 0
    for r in rows:
        if not isinstance(r, dict):
            unrecognized += 1
            continue
        fmt = detect_format(r)
        if fmt is None:
            unrecognized += 1
            continue
        formats[fmt] = formats.get(fmt, 0) + 1
        nr = normalize_row(r, fmt)
        if nr is None:
            unrecognized += 1
            continue
        normalized.append(nr)
    out = {"format": next(iter(formats), "unresolved"),
           "formats_seen": formats,
           "rows": normalized,
           "counts": {"rows_in": len(rows), "normalized": len(normalized),
                      "unrecognized": unrecognized}}
    if not normalized and rows:
        out["unresolved"] = "billing format not recognized — no rows " \
                            "normalized; no costs reported"
    return out
