"""Playbook — coordinator decomposition as steps (works with zero dispatch;
the floor for hosts without subagents)."""

from __future__ import annotations

from typing import Any

from platformforge.agents.roster import AGENTS, coordinator_for


def playbook(coordinator: str = "platform-coordinator",
             domain: str | None = None) -> dict[str, Any]:
    if domain and coordinator == "platform-coordinator":
        spec = coordinator_for(domain) or AGENTS[coordinator]
    else:
        spec = AGENTS.get(coordinator)
        if spec is None:
            return {"refusal": "platform.agent.unresolved",
                    "unlock": f"agents list — {coordinator!r} not in roster"}
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
    if spec.role == "coordinator":
        steps.insert(1, {"step": 1.5, "verb": "route",
                         "why": "pick specialists via routing signals"})
        steps[0]["step"] = 1
    return {"agent": spec.name, "role": spec.role,
            "steps": steps, "executors": list(spec.executors),
            "access": spec.access,
            "contract": {"when": spec.when, "never": spec.never,
                         "outputs": list(spec.outputs)}}
