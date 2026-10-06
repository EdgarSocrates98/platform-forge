"""Agent layer — canonical roster, host mirrors, referee, playbooks.

Agents propose; they never mutate. Every host mirror (.claude/, .agents/,
.codex/) is GENERATED from this roster — never hand-edited."""

from platformforge.agents.playbook import playbook
from platformforge.agents.referee import referee
from platformforge.agents.roster import AGENTS, AgentSpec, coordinator_for

__all__ = ["AGENTS", "AgentSpec", "coordinator_for", "referee", "playbook"]
