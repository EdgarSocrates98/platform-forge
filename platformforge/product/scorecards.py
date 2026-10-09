"""Scorecards v2 — §81 nine axes per entity. An axis with no evidence is
`unknown`, never zero: zero would mean "checked and failed", unknown means
"we don't know". Scores are evidence: each grade lists driving findings.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

_WEIGHT = {"info": 0, "low": 1, "medium": 3, "high": 7, "critical": 15}

# §81 axes — rule_id prefix/domain → axes the finding speaks to
AXES = ("ownership", "security", "reliability", "observability",
        "supply_chain", "cost", "documentation", "deployment",
        "operational_readiness")

_DOMAIN_AXES: dict[str, tuple[str, ...]] = {
    "k8s": ("deployment", "reliability", "operational_readiness"),
    "gitops": ("deployment", "operational_readiness"),
    "cicd": ("deployment", "supply_chain"),
    "security": ("security", "supply_chain"),
    "iam": ("security",),
    "secrets": ("security",),
    "sbom": ("supply_chain",),
    "supply": ("supply_chain",),
    "finops": ("cost",),
    "sre": ("reliability", "observability", "operational_readiness"),
    "slo": ("reliability", "observability"),
    "otel": ("observability",),
    "iac": ("deployment", "security"),
    "product": ("ownership", "documentation"),
    "catalog": ("ownership", "documentation"),
}


def scorecard(findings: list[dict[str, Any]],
              evidence_domains: set[str] | None = None) -> dict[str, Any]:
    """§81 — per-entity, per-axis. `evidence_domains` names the domains
    that produced facts (a domain with no findings but which *was*
    measured is measurably clean, not unknown)."""
    per: dict[str, dict[str, list[dict]]] = defaultdict(
        lambda: defaultdict(list))
    seen_domains: set[str] = set(evidence_domains or ())
    for f in findings:
        if f.get("status") != "violated":
            continue
        dom = (f.get("rule_id") or "").split("-")[1].lower() \
            if "-" in (f.get("rule_id") or "") else ""
        loc = f.get("location") or "unknown"
        seen_domains.add(dom)
        for axis in _DOMAIN_AXES.get(dom, ("operational_readiness",)):
            per[loc][axis].append(f)

    cards = {}
    for loc, axes in sorted(per.items()):
        ax = {}
        for axis in AXES:
            fs = axes.get(axis, [])
            if not fs:
                # unknown ≠ zero: report which domains could have produced
                # evidence for this axis, and whether any was measured
                producers = [d for d, a in _DOMAIN_AXES.items()
                             if axis in a]
                ax[axis] = {
                    "status": "clean" if any(p in seen_domains
                                             for p in producers)
                              else "unknown",
                    "score": None if not any(p in seen_domains
                                             for p in producers) else 100}
                continue
            penalty = sum(_WEIGHT.get(f.get("severity", "info"), 0)
                          for f in fs)
            score = max(0, 100 - penalty)
            ax[axis] = {"status": "measured", "score": score,
                        "driving_findings": [f.get("rule_id") for f in fs]}
        known = [a["score"] for a in ax.values() if a["score"] is not None]
        overall = round(sum(known) / len(known)) if known else None
        cards[loc] = {"axes": ax, "overall": overall,
                      "unknown_axes": [a for a in AXES
                                       if ax[a]["status"] == "unknown"],
                      "total_violations": sum(len(v) for v in axes.values())}
    return {"scorecards": cards, "count": len(cards), "axes": list(AXES),
            "note": "unknown axis = no measured evidence, not a zero score"}
