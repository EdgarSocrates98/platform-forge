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

    # §136–137 — information gain / stagnation: group positions by round;
    # a round that adds no new evidence ids signals "stop" — later rounds
    # are trimmed (deterministic bound, no unlimited debate).
    by_round: dict[int, list[DebatePosition]] = {}
    for p in pos:
        by_round.setdefault(p.round, []).append(p)
    seen_evidence: set[str] = set()
    kept: list[DebatePosition] = []
    stagnant_at: int | None = None
    for rnd in sorted(by_round):
        new_ids = {e for p in by_round[rnd] for e in p.evidence}
        gain = new_ids - seen_evidence
        if rnd > 0 and not gain:
            stagnant_at = rnd
            break                       # §137 — no new evidence → stop
        seen_evidence |= new_ids
        kept.extend(by_round[rnd])
    pos = kept

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
    out["stopped_early"] = stagnant_at is not None   # §135–137
    if stagnant_at is not None:
        out["stagnant_round"] = stagnant_at
        out["stop_reason"] = "no information gain — round added no new evidence ids"
    if envelope_budget is not None:
        out["budget"] = envelope_budget
    if outcome == "unresolved":
        return {**refusal(AgentRefusal.DEBATE_UNRESOLVED,
                          "no position carried enough evidence to win",
                          "gather more evidence or escalate to a human "
                          "— the gap is real, not a tie-break problem"),
                "debate": out}
    return {"debate": out, "verifier_required": True}


def build_referee_packet(positions: list[dict[str, Any] | DebatePosition],
                         *, budget: dict[str, Any] | None = None
                         ) -> dict[str, Any]:
    """§131–133 — RefereePacket: the compressed structured view the
    referee receives. Positions + deltas + shared evidence +
    contradictions + budget — never the full transcript."""
    pos = [p if isinstance(p, DebatePosition) else DebatePosition(
        agent=p.get("agent", ""), claim=p.get("claim", ""),
        evidence=tuple(p.get("evidence") or p.get("evidence_fact_ids") or ()),
        round=p.get("round", 0)) for p in positions]
    evidence_counts: dict[str, int] = {}
    for p in pos:
        for e in p.evidence:
            evidence_counts[e] = evidence_counts.get(e, 0) + 1
    shared = sorted(e for e, n in evidence_counts.items() if n > 1)
    # contradictions = claims citing the same evidence id to opposing ends
    # is unresolvable deterministically here; contradictions are the
    # pairwise claim/delta surface the referee must adjudicate.
    deltas = [{"agent": p.agent, "claim": p.claim,
               "own_evidence": sorted(set(p.evidence) - set(shared))}
              for p in pos]
    return {"schema": "platformforge/referee-packet/v1",
            "positions": [{"agent": p.agent, "claim": p.claim,
                           "evidence": list(p.evidence),
                           "round": p.round} for p in pos],
            "shared_evidence": shared,
            "deltas": deltas,
            "contradictions": "declared by position evidence overlap",
            "budget": budget or {},
            "note": "no full transcript — referee adjudicates structure"}
