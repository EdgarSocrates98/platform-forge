"""platform-debate-referee — deterministic adjudication (cycle5.1 §24–26).

Positions are scored on ten declared axes, never averaged into mush:

    tier                 evidence tier (lower wins)
    freshness            source/claim freshness (current|fresh|stale|...)
    version_compat       does the claim's version basis match context
    scope                does the claim cover the asked scope
    contradictory        count of unresolved contradictions against it
    completeness         fraction of required evidence fields present
    coverage             fraction of asked scope the evidence covers
    runtime_alignment    claim consistent with runtime evidence
    risk                 accepting a risky claim needs stronger evidence
    historical_support   claim supported by history patterns

A position with no evidence loses regardless of prose confidence. Ties
and gaps are explicit in the receipt; the referee never averages
positions into a compromise (§26).
"""

from __future__ import annotations

from typing import Any

from platformforge.models.base import stable_id

_FRESH = {"current": 0, "fresh": 1, "stale": 3,
          "deprecated": 5, "superseded": 5, "conflicted": 4,
          "unresolved": 6}

# weight per axis — evidence still dominates, but the §25 axes all move
# the score (§115 + cycle5.1 expansion: coverage, runtime alignment,
# risk, historical support)
_W = {"tier": 10.0, "freshness": 3.0, "version_compat": 4.0,
      "scope": 3.0, "contradictory": 8.0, "completeness": 4.0,
      "coverage": 4.0, "runtime_alignment": 4.0, "risk": 6.0,
      "historical_support": 2.0}

_REQUIRED_EVIDENCE_FIELDS = ("fact_id", "kind", "tier")

_RISK = {"low": 0.0, "medium": 1.0, "high": 2.0, "critical": 3.0}


def _tri(value: Any) -> float:
    """tri-state: True→1.0, False→0.0, unknown/absent→0.5."""
    return 1.0 if value is True else 0.0 if value is False else 0.5


def _completeness(p: dict[str, Any]) -> float:
    """Fraction of positions' evidence refs that resolve to full facts."""
    ev = p.get("evidence_facts") or []
    if not ev:
        return 0.0
    full = sum(1 for e in ev
               if isinstance(e, dict)
               and all(e.get(k) is not None
                       for k in _REQUIRED_EVIDENCE_FIELDS))
    return full / len(ev)


def _score(p: dict[str, Any]) -> dict[str, Any]:
    tier = p.get("evidence_tier", 7)
    try:
        tier = min(max(int(tier), 0), 7)
    except (TypeError, ValueError):
        tier = 7
    freshness = _FRESH.get(str(p.get("freshness", "unresolved")).lower(), 6)
    vc = _tri(p.get("version_compat"))
    scope = _tri(p.get("scope_match"))
    contradictions = len(p.get("contradictions") or [])
    completeness = _completeness(p)
    coverage = p.get("coverage")
    try:
        coverage = min(max(float(coverage), 0.0), 1.0)
    except (TypeError, ValueError):
        coverage = 0.0
    runtime = _tri(p.get("runtime_alignment"))
    risk = _RISK.get(str(p.get("risk", "low")).lower(), 0.0)
    history = _tri(p.get("historical_support"))

    ev = p.get("evidence_fact_ids") or p.get("evidence") or []
    has_ev = bool(ev) or completeness > 0
    score = (100.0 if has_ev else 0.0)
    score -= _W["tier"] * tier
    score -= _W["freshness"] * freshness
    score += _W["version_compat"] * vc
    score += _W["scope"] * scope
    score -= _W["contradictory"] * min(contradictions, 3)
    score += _W["completeness"] * completeness
    score += _W["coverage"] * coverage
    score += _W["runtime_alignment"] * runtime
    # risk penalizes a weak-evidence position, not a cautious one
    score -= _W["risk"] * risk * (1.0 if tier >= 4 else 0.25)
    score += _W["historical_support"] * history
    return {"agent": p.get("agent", "?"), "claim": p.get("claim", ""),
            "tier": tier, "freshness": freshness,
            "version_compat": vc, "scope": scope,
            "contradictions": contradictions,
            "completeness": round(completeness, 3),
            "coverage": round(coverage, 3),
            "runtime_alignment": runtime,
            "risk": p.get("risk", "low"),
            "historical_support": history,
            "evidence_count": len(ev), "score": round(score, 3),
            "evidence": ev}


def referee(positions: list[dict[str, Any]]) -> dict[str, Any]:
    """positions: [{agent, claim, evidence_fact_ids|evidence_facts,
    evidence_tier, freshness, version_compat, scope_match, coverage,
    runtime_alignment, risk, historical_support, contradictions, ...}]
    → winner + receipt. Ties/gaps explicit."""
    scored = [_score(p) for p in positions]
    scored.sort(key=lambda s: -s["score"])
    winner = scored[0] if scored else None
    tied = [s for s in scored if winner and s["score"] == winner["score"]]
    winner_has_ev = bool(winner and (winner["evidence"]
                                     or winner["completeness"] > 0))
    return {
        "winner": winner,
        "tied": len(tied) > 1,
        "positions": scored,
        "unresolved": winner is None or not winner_has_ev,
        "receipt": {"refusal_code": None if winner_has_ev
                    else "platform.evidence.unresolved",
                    "receipt_id": stable_id(
                        "PF-REF", str(len(positions)),
                        ",".join(sorted(p.get("agent", "?")
                                        for p in positions)))},
        "axes": sorted(_W),
        "note": "ten declared axes decide; no position is averaged away",
    }
