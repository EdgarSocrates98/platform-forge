"""Coordinator machinery — bounded dispatch + collection (§28–34, §67).

Coordinators may dispatch (only orchestrators/coordinators create
fan-out, §67); specialists may not spawn. A coordinator's dispatch plan
is deterministic: TaskSpec domains ∩ coordinator delegates_to →
AgentHandoff list. Collection merges handoffs without minting facts.
"""

from __future__ import annotations

from typing import Any

from platformforge.agents.contracts import AgentHandoff, AgentRefusal, PlatformTaskSpec, refusal
from platformforge.agents.roster import resolve
from platformforge.models.base import stable_id

# coordinator → its canonical loop in rules/catalog/orchestration.yaml
COORDINATOR_LOOPS = {
    "platform-incident-coordinator": "incident",
    "platform-change-coordinator": "change",
    "platform-fleet-coordinator": "fleet",
    "platform-optimization-coordinator": "optimization",
    "platform-product-coordinator": "platform-audit",
}


def dispatch_plan(coordinator: str, spec: PlatformTaskSpec) \
        -> dict[str, Any]:
    """coordinator + sealed spec → handoffs to delegated specialists.

    Only delegates whose declared domains intersect the task's are
    dispatched — a coordinator never fans out to its whole delegate
    list 'just in case' (§68 companion)."""
    coord = resolve(coordinator)
    if coord is None:
        return refusal(AgentRefusal.UNKNOWN_AGENT,
                       f"no agent named {coordinator!r}",
                       "check the canonical roster")
    if coord.role not in ("coordinator", "orchestrator"):
        return refusal(
            AgentRefusal.HOST_CAPABILITY,
            f"{coordinator} is role={coord.role} — only orchestrators "
            "and coordinators may dispatch (§67)",
            "route through platform-orchestrator")
    targets = [d for d in coord.delegates_to
               if resolve(d) is not None
               and (not spec.domains
                    or set(resolve(d).domains) & set(spec.domains)
                    or "all" in resolve(d).domains)]
    if not targets:
        return refusal(
            AgentRefusal.ROUTE_UNRESOLVED,
            f"{coordinator} has no delegate covering domains "
            f"{sorted(spec.domains)}",
            "widen the spec domains or escalate to the orchestrator")
    # §67/§113 — fanout is bounded: never dispatch past the
    # coordinator's declared parallelism; the remainder stays queued
    capped = targets[:coord.max_parallelism]
    queued = targets[coord.max_parallelism:]
    handoffs = []
    for t in capped:
        handoffs.append(AgentHandoff(
            sender=coordinator, to=t, task_id=spec.task_id,
            reason=f"dispatch: {spec.intent[:80]}",
            open_questions=tuple(c for c in spec.acceptance_criteria),
            budget_spent={},
            next_required_capability="",
            context_pack_ref="", ))
    return {"coordinator": coordinator,
            "loop": COORDINATOR_LOOPS.get(coord.name, "platform-audit"),
            "dispatched": capped,
            "queued": queued,
            "handoffs": [h.to_dict() for h in handoffs],
            "bounded": not queued}


def collect(handoffs: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge specialist handoffs — completed/evidence/unresolved.
    Collecting is bookkeeping, not adjudication: conflicts go to the
    referee, gaps stay unresolved (§98 vocabulary)."""
    done, ev, unresolved, questions = set(), set(), set(), set()
    for h in handoffs:
        done.update(h.get("completed") or ())
        ev.update(h.get("evidence") or ())
        unresolved.update(h.get("unresolved") or ())
        questions.update(h.get("open_questions") or ())
    return {"completed": sorted(done), "evidence": sorted(ev),
            "unresolved": sorted(unresolved),
            "open_questions": sorted(questions),
            "responded": len(handoffs),
            "collection_id": stable_id(
                "PF-COLL", str(len(handoffs)),
                ",".join(sorted(ev)))}


def coordinator_loop(name: str) -> str:
    """Coordinator name → canonical loop; orchestrator → audit."""
    return COORDINATOR_LOOPS.get(name, "platform-audit")
