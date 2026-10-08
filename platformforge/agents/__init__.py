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
from platformforge.agents.coordinators import (
    COORDINATOR_LOOPS,
    collect,
    coordinator_loop,
    dispatch_plan,
)
from platformforge.agents.critic import adversarial_review, pre_mortem
from platformforge.agents.executors import (
    EXECUTORS,
    pf_extract,
    pf_graph_build,
    pf_inventory,
    pf_judge,
    pf_reconcile,
    pf_simulate,
    pf_synthesize,
    pf_verify,
)
from platformforge.agents.guardian import release_review
from platformforge.agents.orchestrator import (
    DagNode,
    OrchestrationPlan,
    build_dag,
    checkpoint,
    load_loops,
    prepare,
    resume,
    validate_dag,
)
from platformforge.agents.planner import plan
from platformforge.agents.playbook import playbook
from platformforge.agents.referee import referee
from platformforge.agents.reviewers import (
    OPS_SAFETY_CHECKLIST,
    architecture_review,
    ops_safety_review,
    privacy_review,
    security_review,
)
from platformforge.agents.roster import AGENTS, AgentSpec, coordinator_for, resolve
from platformforge.agents.specialists import finding, grade
from platformforge.agents.taskspec import (
    expire,
    require_sealed,
    review,
    seal,
)
from platformforge.agents.verifier import verify_run

__all__ = [
    "ACCESS_TIERS",
    "AGENTS",
    "BUDGET_CLASSES",
    "COORDINATOR_LOOPS",
    "EXECUTORS",
    "MODEL_TIERS",
    "OPS_SAFETY_CHECKLIST",
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
    "DagNode",
    "Debate",
    "DebatePosition",
    "OrchestrationPlan",
    "PlatformTaskSpec",
    "adversarial_review",
    "architecture_review",
    "build_dag",
    "checkpoint",
    "collect",
    "coordinator_for",
    "coordinator_loop",
    "dispatch_plan",
    "envelope_for",
    "expire",
    "finding",
    "grade",
    "load_loops",
    "ops_safety_review",
    "pf_extract",
    "pf_graph_build",
    "pf_inventory",
    "pf_judge",
    "pf_reconcile",
    "pf_simulate",
    "pf_synthesize",
    "pf_verify",
    "plan",
    "playbook",
    "pre_mortem",
    "prepare",
    "privacy_review",
    "referee",
    "refusal",
    "release_review",
    "require_sealed",
    "resolve",
    "resume",
    "review",
    "seal",
    "security_review",
    "validate_dag",
    "verify_run",
]
