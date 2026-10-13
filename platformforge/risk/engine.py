"""Change-risk assessment — §130.

Inputs are signals, each scored 0-3 and weighted. Output is a level with a
full decomposition — never a bare number. Criticality is taken from
*declared* signals (labels, owning findings, graph exposure); business
criticality is never inferred from technology alone (§131).
"""

from __future__ import annotations

from typing import Any

LEVELS = ("low", "medium", "high", "critical")

# signal → (weight, scorer description)
SIGNALS = {
    "blast_radius": 3,        # # of impacted nodes per impact class
    "criticality": 3,         # declared criticality of touched nodes
    "production": 2,          # environment == production
    "security_impact": 3,     # security findings in blast radius
    "identity_impact": 3,     # IAM/principal changes
    "network_exposure": 2,    # new public/exposed surface
    "data_persistence": 2,    # touches db/bucket/volume
    "availability_impact": 2, # touches workload/slo-bearing nodes
    "cost_impact": 1,         # billed delta detected
    "reversibility": 2,       # destructive/replacing change → 0
    "test_coverage": 1,       # tests/verification present → lowers
}

_THRESHOLDS = [(8, "low"), (16, "medium"), (26, "high"), (10**9, "critical")]


def _level(score: int) -> str:
    for cap, name in _THRESHOLDS:
        if score <= cap:
            return name
    return "critical"


def assess_change(signals: dict[str, Any]) -> dict[str, Any]:
    """signals: dict of declared values; unknown signals are *unresolved*,
    scored 0 and listed — never silently assumed safe."""
    unknown = {k for k in signals if k not in SIGNALS}
    decomposition: dict[str, dict[str, Any]] = {}
    total = 0
    for sig, weight in SIGNALS.items():
        v = signals.get(sig)
        if v is None:
            decomposition[sig] = {"value": "unresolved", "score": 0,
                                  "weight": weight}
            continue
        if isinstance(v, bool):
            # True = protective for reversibility/test_coverage; risk for rest
            raw = (0 if v else 3) if sig in ("reversibility", "test_coverage") \
                else (3 if v else 0)
        elif isinstance(v, (int, float)):
            raw = min(3, max(0, int(v)))
        else:
            raw = {"none": 0, "low": 1, "medium": 2, "high": 3,
                   "critical": 3}.get(str(v).lower(), 0)
        decomposition[sig] = {"value": v, "score": raw, "weight": weight}
        total += raw * weight
    unresolved = [s for s, d in decomposition.items()
                  if d["value"] == "unresolved"]
    # §103 — unknown ≠ low risk: unresolved signals don't zero the level,
    # they flag confidence and can only raise the reported level, never
    # lower it. A "low" with unresolved signals is a claim, not a fact.
    confidence = round(1.0 - len(unresolved) / len(SIGNALS), 3)
    if unresolved and _level(total) in ("low", "medium"):
        note = ("risk is underreported: unresolved signals could "
                "raise the level")
    else:
        note = ("criticality is taken from declared signals only; "
                "absence of a signal lowers confidence, not safety")
    return {
        "level": _level(total),
        "score": total,
        "confidence": confidence,
        "underreported": bool(unresolved and _level(total) != "critical"),
        "decomposition": decomposition,
        "unknown_signals": sorted(unknown),
        "unresolved": unresolved,
        "note": note,
    }


def criticality(node_attrs: dict[str, Any]) -> str:
    """Declared criticality only — tier labels, never tech-inferred."""
    for k in ("criticality", "tier", "criticality_tier"):
        v = str(node_attrs.get(k) or "").lower()
        if v in ("critical", "high", "medium", "low", "tier0", "tier1",
                 "tier2", "tier3"):
            return {"tier0": "critical", "tier1": "high",
                    "tier2": "medium", "tier3": "low"}.get(v, v)
    return "unresolved"
