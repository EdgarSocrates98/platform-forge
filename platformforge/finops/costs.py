"""Cost facts — ingest billing exports (JSON/CSV rows) into `finops.cost`
facts and aggregates. Currency/period mismatches surface as unresolved."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from platformforge.models.base import stable_id

REQ_FIELDS = ("resource", "amount")
OPT_FIELDS = ("service", "period", "currency", "unit", "tags")


def _rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix == ".csv":
        return list(csv.DictReader(path.open()))
    doc = json.loads(path.read_text())
    return doc if isinstance(doc, list) else doc.get("rows", [])


def cost_facts_from_rows(rows: list[dict[str, Any]],
                         source: str = "rows") -> dict[str, Any]:
    """Row list → finops.cost facts (shared by file + ingest paths)."""
    facts: list[dict[str, Any]] = []
    skipped = 0
    for r in rows:
        if not all(r.get(k) not in (None, "") for k in REQ_FIELDS):
            skipped += 1
            continue
        tags = r.get("tags")
        if isinstance(tags, str):
            try:
                tags = json.loads(tags)
            except json.JSONDecodeError:
                tags = {}
        attrs = {"resource": r["resource"],
                 "amount": float(r["amount"]),
                 "currency": r.get("currency") or "USD",
                 "period": r.get("period") or "unknown",
                 "service": r.get("service"),
                 "tags": tags or {}}
        facts.append({"fact_id": stable_id("PF-FIN", r["resource"],
                                           str(r.get("period")),
                                           str(r["amount"])),
                      "kind": "finops.cost", "source": source,
                      "location": r["resource"], "tier": 1, "attrs": attrs})
    return {"facts": facts,
            "counts": {"rows": len(rows), "facts": len(facts),
                       "skipped_incomplete": skipped}}


def cost_facts(path: str | Path) -> dict[str, Any]:
    return cost_facts_from_rows(_rows(Path(path)), source=str(path))


def cost_summary(facts: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate by period/service/currency; mixed currencies → unresolved."""
    by_period: dict[str, dict[str, float]] = defaultdict(
        lambda: defaultdict(float))
    currencies: set[str] = set()
    for f in facts:
        if f.get("kind") != "finops.cost":
            continue
        a = f["attrs"]
        currencies.add(a["currency"])
        by_period[a["period"]][a.get("service") or "unknown"] += a["amount"]
    out = {"by_period": {p: dict(svcs) for p, svcs in sorted(by_period.items())},
           "currencies": sorted(currencies)}
    if len(currencies) > 1:
        out["unresolved"] = "mixed currencies — totals withheld"
    else:
        out["total"] = round(
            sum(f["attrs"]["amount"] for f in facts
                if f.get("kind") == "finops.cost"), 4)
    return out
