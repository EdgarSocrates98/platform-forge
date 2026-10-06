"""Referee — deterministic adjudication between competing findings.

Ranking: evidence tier (lower number wins) → measured beats declared beats
inferred → unresolved is reported, not averaged away."""

from __future__ import annotations

from typing import Any

from platformforge.models.base import stable_id


def referee(positions: list[dict[str, Any]]) -> dict[str, Any]:
    """positions: [{agent, claim, evidence_fact_ids, evidence_tier, ...}].
    Returns the winner + receipt; ties and evidence gaps are explicit."""
    scored = []
    for p in positions:
        tier = p.get("evidence_tier", 7)
        try:
            tier = int(tier)
        except (TypeError, ValueError):
            tier = 7
        ev = p.get("evidence_fact_ids") or p.get("evidence") or []
        scored.append({
            "agent": p.get("agent", "?"),
            "claim": p.get("claim", ""),
            "tier": tier,
            "evidence_count": len(ev),
            "score": (0 if not ev else 1) * 100 - tier,
            "evidence": ev,
        })
    scored.sort(key=lambda s: -s["score"])
    winner = scored[0] if scored else None
    tied = [s for s in scored if winner and s["score"] == winner["score"]]
    return {
        "winner": winner,
        "tied": len(tied) > 1,
        "positions": scored,
        "unresolved": winner is None or (winner and not winner["evidence"]),
        "receipt": {"refusal_code": None if winner and winner["evidence"]
                    else "platform.evidence.unresolved",
                    "receipt_id": stable_id(
                        "PF-REF", str(len(positions)),
                        ",".join(sorted(p.get("agent", "?")
                                        for p in positions)))},
        "note": "evidence tier decides; no position is averaged away",
    }
