"""Referee v2 (§115) — deterministic adjudication between positions.

Positions are scored on six declared axes, never averaged into mush:

    tier                 evidence tier (lower wins)
    freshness            source/claim freshness (current|fresh|stale|...)
    version_compat       does the claim's version basis match context
    scope                does the claim cover the asked scope
    contradictory        count of unresolved contradictions against it
    completeness         fraction of required evidence fields present

A position with no evidence loses regardless of prose confidence. Ties and
gaps are explicit in the receipt.
"""

from __future__ import annotations

from typing import Any

from platformforge.models.base import stable_id

_FRESH = {"current": 0, "fresh": 1, "stale": 3,
          "deprecated": 5, "superseded": 5, "conflicted": 4,
          "unresolved": 6}

# weight per axis — evidence still dominates, but freshness/version/scope/
# contradictions/completeness now move the score (§115)
_W = {"tier": 10.0, "freshness": 3.0, "version_compat": 4.0,
      "scope": 3.0, "contradictory": 8.0, "completeness": 4.0}

_REQUIRED_EVIDENCE_FIELDS = ("fact_id", "kind", "tier")


def _completeness(p: dict[str, Any]) -> float:
    """Fraction of positions' evidence refs that resolve to full facts."""
    ev = p.get("evidence_facts") or []
    if not ev:
        return 0.0
    full = sum(1 for e in ev
               if isinstance(e, dict)
               and all(e.get(k) is not None for k in _REQUIRED_EVIDENCE_FIELDS))
    return full / len(ev)


def _score(p: dict[str, Any]) -> dict[str, Any]:
    tier = p.get("evidence_tier", 7)
    try:
        tier = min(max(int(tier), 0), 7)
    except (TypeError, ValueError):
        tier = 7
    freshness = _FRESH.get(str(p.get("freshness", "unresolved")).lower(), 6)
    # version_compat: 1.0 ok, 0.5 unknown, 0.0 incompatible
    vc = p.get("version_compat")
    vc = 1.0 if vc is True else 0.0 if vc is False else 0.5
    scope = p.get("scope_match")
    scope = 1.0 if scope is True else 0.0 if scope is False else 0.5
    contradictions = len(p.get("contradictions") or [])
    completeness = _completeness(p)

    ev = p.get("evidence_fact_ids") or p.get("evidence") or []
    has_ev = bool(ev) or completeness > 0
    score = (100.0 if has_ev else 0.0)
    score -= _W["tier"] * tier
    score -= _W["freshness"] * freshness
    score += _W["version_compat"] * vc
    score += _W["scope"] * scope
    score -= _W["contradictory"] * min(contradictions, 3)
    score += _W["completeness"] * completeness
    return {"agent": p.get("agent", "?"), "claim": p.get("claim", ""),
            "tier": tier, "freshness": freshness,
            "version_compat": vc, "scope": scope,
            "contradictions": contradictions,
            "completeness": round(completeness, 3),
            "evidence_count": len(ev), "score": round(score, 3),
            "evidence": ev}


def referee(positions: list[dict[str, Any]]) -> dict[str, Any]:
    """positions: [{agent, claim, evidence_fact_ids|evidence_facts,
    evidence_tier, freshness, version_compat, scope_match,
    contradictions, ...}] → winner + receipt. Ties/gaps explicit."""
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
        "note": "six declared axes decide; no position is averaged away",
    }
