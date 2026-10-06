"""Scorecards — findings rolled up per entity. Score is evidence, not vibe:
each grade lists the finding_ids that drove it."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

_WEIGHT = {"info": 0, "low": 1, "medium": 3, "high": 7, "critical": 15}


def scorecard(findings: list[dict[str, Any]]) -> dict[str, Any]:
    """Group violated findings by location → score per entity."""
    per: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for f in findings:
        if f.get("status") != "violated":
            continue
        per[f.get("location") or "unknown"].append(f)
    cards = {}
    for loc, fs in sorted(per.items()):
        penalty = sum(_WEIGHT.get(f.get("severity", "info"), 0) for f in fs)
        score = max(0, 100 - penalty)
        grade = "A" if score >= 90 else "B" if score >= 75 else \
            "C" if score >= 60 else "D" if score >= 40 else "F"
        cards[loc] = {
            "score": score, "grade": grade,
            "violations": len(fs),
            "by_severity": {s: sum(1 for f in fs if f.get("severity") == s)
                            for s in _WEIGHT
                            if any(f.get("severity") == s for f in fs)},
            "driving_findings": [f.get("rule_id") for f in fs],
        }
    return {"scorecards": cards, "count": len(cards)}
