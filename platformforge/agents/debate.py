"""Debate engine — bounded disagreement between positions (§126–133).

Shape is small by default: ≤4 participants (typically 2 specialists +
1 critic), ≤3 rounds, inside the run envelope. Every position must cite
evidence — a position without evidence is refused, not debated. The
referee adjudicates on declared axes and returns a receipt; a resolved
debate still requires the independent verifier afterward (§133).
"""

from __future__ import annotations

from typing import Any

from platformforge.agents.contracts import AgentRefusal, Debate, DebatePosition, refusal
from platformforge.agents.referee import referee

DEFAULT_MAX_PARTICIPANTS = 4
DEFAULT_MAX_ROUNDS = 3


def _position_errors(p: DebatePosition) -> list[str]:
    errs = []
    if not p.agent:
        errs.append("position missing agent")
    if not p.claim:
        errs.append(f"{p.agent or '?'}: claim is empty")
    if not p.evidence:
        errs.append(f"{p.agent or '?'}: position cites no evidence "
                    "(§131 — evidence is required to debate)")
    return errs


def run_debate(question: str, positions: list[dict[str, Any] |
               DebatePosition], *, max_rounds: int = DEFAULT_MAX_ROUNDS,
               max_participants: int = DEFAULT_MAX_PARTICIPANTS,
               envelope_budget: dict[str, Any] | None = None,
               ) -> dict[str, Any]:
    """Adjudicate positions through the referee under explicit bounds.

    positions: dicts with at least {agent, claim, evidence}. Rounds are
    the positions' declared `round` field — a debate never exceeds
    max_rounds or max_participants; over-bounds input is refused, not
    silently truncated.
    """
    if not question.strip():
        return refusal(AgentRefusal.NO_EVIDENCE,
                       "debate has no question",
                       "state the contested claim precisely")
    pos = [p if isinstance(p, DebatePosition) else DebatePosition(
        agent=p.get("agent", ""), claim=p.get("claim", ""),
        evidence=tuple(p.get("evidence") or p.get("evidence_fact_ids") or ()),
        evidence_tier=p.get("evidence_tier", 7),
        freshness=p.get("freshness", "unresolved"),
        round=p.get("round", 0)) for p in positions]
    participants = {p.agent for p in pos}
    if len(participants) > max_participants:
        return refusal(AgentRefusal.DEBATE_UNRESOLVED,
                       f"{len(participants)} participants exceeds bound "
                       f"{max_participants} — debates are small, not swarms",
                       "drop to the 2 strongest positions + critic")
    if any(p.round > max_rounds for p in pos):
        return refusal(AgentRefusal.DEBATE_UNRESOLVED,
                       f"a position declares a round beyond {max_rounds}",
                       "re-run inside the 1–3 round bound")
    errs = [e for p in pos for e in _position_errors(p)]
    if errs:
        return refusal(AgentRefusal.NO_EVIDENCE, "; ".join(errs),
                       "every position must cite at least one evidence "
                       "ref — unsupported positions are dropped, not "
                       "debated")
    if not pos:
        return refusal(AgentRefusal.NO_EVIDENCE,
                       "no positions to adjudicate",
                       "collect positions first")

    decision = referee([{"agent": p.agent, "claim": p.claim,
                         "evidence": list(p.evidence),
                         "evidence_tier": p.evidence_tier,
                         "freshness": p.freshness, "round": p.round}
                        for p in pos])
    outcome = ("unresolved" if decision["unresolved"]
               else "tied" if decision["tied"] else "winner")
    debate = Debate(debate_id=decision["receipt"]["receipt_id"],
                    question=question, positions=tuple(pos),
                    max_participants=max_participants,
                    max_rounds=max_rounds,
                    round=max(p.round for p in pos),
                    outcome=outcome,
                    winner=(decision["winner"] or {}).get("agent", ""),
                    axes=tuple(decision["axes"]),
                    receipt={**decision["receipt"],
                             "positions": decision["positions"],
                             "verifier_required": True,
                             "note": "referee adjudicates disagreement; "
                                     "verification is still a separate "
                                     "independent step (§133)"})
    out = debate.to_dict()
    if envelope_budget is not None:
        out["budget"] = envelope_budget
    if outcome == "unresolved":
        return {**refusal(AgentRefusal.DEBATE_UNRESOLVED,
                          "no position carried enough evidence to win",
                          "gather more evidence or escalate to a human "
                          "— the gap is real, not a tie-break problem"),
                "debate": out}
    return {"debate": out, "verifier_required": True}
