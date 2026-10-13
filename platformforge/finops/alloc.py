"""Tag-based cost allocation — spend grouped by a tag dimension; untagged
spend is surfaced as unallocated, never silently dropped."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def allocate(facts: list[dict[str, Any]], by: str = "cost_center") \
        -> dict[str, Any]:
    buckets: dict[str, float] = defaultdict(float)
    unalloc: list[str] = []
    for f in facts:
        if f.get("kind") != "finops.cost":
            continue
        a = f["attrs"]
        key = (a.get("tags") or {}).get(by)
        if key:
            buckets[key] += a["amount"]
        else:
            buckets["UNALLOCATED"] += a["amount"]
            unalloc.append(a["resource"])
    total = sum(buckets.values())
    return {"by": by,
            "allocation": {k: round(v, 4) for k, v in sorted(buckets.items())},
            "shares": {k: round(v / total, 4) for k, v in
                       sorted(buckets.items())} if total else {},
            "unallocated_resources": sorted(set(unalloc)),
            "unallocated_amount": round(buckets.get("UNALLOCATED", 0.0), 4),
            "total": round(total, 4)}
