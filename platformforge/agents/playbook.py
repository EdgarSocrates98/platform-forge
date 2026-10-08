"""Playbook — coordinator decomposition as sequential steps.

This is the zero-subagent floor (§166–170): a host without native agent
delegation runs the same plan as explicit phases, with identical
evidence requirements. Nothing about the run becomes unverifiable when
fan-out is unavailable — the orchestrator's DAG degrades to a list.
"""

from __future__ import annotations

from typing import Any

from platformforge.agents.contracts import AgentRefusal, refusal
from platformforge.agents.roster import AGENTS, coordinator_for, resolve


def playbook(coordinator: str = "platform-orchestrator",
             domain: str | None = None) -> dict[str, Any]:
    if domain and coordinator == "platform-orchestrator":
        spec = coordinator_for(domain) or AGENTS[coordinator]
    else:
        spec = resolve(coordinator)
        if spec is None:
            return refusal(
                AgentRefusal.UNKNOWN_AGENT,
                f"{coordinator!r} is not in the canonical roster",
                "agents list — pick a name that exists")
    steps = [
        {"step": 1, "verb": "inspect", "why": "inventory artifacts"},
        {"step": 2, "verb": f"analyze ({', '.join(spec.domains)})",
         "why": "facts over the domain artifacts"},
        {"step": 3, "verb": "judge", "why": "rules over facts → findings"},
        {"step": 4, "verb": "graph build + gaps",
         "why": "wire provenance, surface structural gaps"},
        {"step": 5, "verb": "economy",
         "why": "report context spend — never claim unmeasured savings"},
    ]
    if spec.role in ("coordinator", "orchestrator"):
        steps.insert(1, {"step": 1.5, "verb": "route",
                         "why": "pick specialists via routing signals"})
        steps[0]["step"] = 1
    return {"agent": spec.name, "role": spec.role,
            "mode": "playbook",
            "steps": steps, "delegates_to": list(spec.delegates_to),
            "access": spec.access,
            "contract": {"when": spec.when_to_enter,
                         "when_not_to_enter": spec.when_not_to_enter,
                         "never": spec.never,
                         "outputs": list(spec.outputs)}}
