"""Agent layer — canonical roster, contracts, host mirrors, referee,
playbooks, orchestration machinery (cycle5.1).

Agents propose; they never mutate. Every host mirror (.claude/, .agents/,
.codex/, .devin/, agents/) is GENERATED from this roster — never
hand-edited. Deterministic engines remain the authority; agents
interpret, coordinate, review, verify and explain.
"""

from platformforge.agents.contracts import (
    ACCESS_TIERS,
    BUDGET_CLASSES,
    MODEL_TIERS,
    OUTPUT_STATUSES,
    ROLES,
    ROUTING_MODES,
    TASK_STATES,
    WRITE_SCOPES,
    AgentHandoff,
    AgentRefusal,
    AgentRunEnvelope,
    AgentRunRecord,
    Debate,
    DebatePosition,
    PlatformTaskSpec,
    envelope_for,
    refusal,
)
from platformforge.agents.playbook import playbook
from platformforge.agents.referee import referee
from platformforge.agents.roster import AGENTS, AgentSpec, coordinator_for, resolve

__all__ = [
    "ACCESS_TIERS",
    "AGENTS",
    "BUDGET_CLASSES",
    "MODEL_TIERS",
    "OUTPUT_STATUSES",
    "ROLES",
    "ROUTING_MODES",
    "TASK_STATES",
    "WRITE_SCOPES",
    "AgentHandoff",
    "AgentRefusal",
    "AgentRunEnvelope",
    "AgentRunRecord",
    "AgentSpec",
    "Debate",
    "DebatePosition",
    "PlatformTaskSpec",
    "coordinator_for",
    "envelope_for",
    "playbook",
    "referee",
    "refusal",
    "resolve",
]
