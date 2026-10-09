"""Agent runtime contracts — canonical, versioned, hashable (cycle5.1).

Everything crossing an agent boundary is a typed document:

    PlatformTaskSpec   sealed intent (draft|reviewed|sealed|rejected|expired)
    AgentHandoff       structured transfer between agents (refs, not bodies)
    AgentRunEnvelope   hard budget limits for one run
    AgentRunRecord     auditable run receipt
    Debate             bounded, evidence-carrying disagreement

Schema ids ship in contracts/*.schema.json and are validated by the
agents-contract gate. None of these documents mutate platform state —
agents propose; governed ops execute.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

SCHEMA_AGENT_SPEC = "platformforge/agent-spec/v1"
SCHEMA_TASK_SPEC = "platformforge/task-spec/v1"
SCHEMA_HANDOFF = "platformforge/agent-handoff/v1"
SCHEMA_RUN = "platformforge/agent-run/v1"
SCHEMA_DEBATE = "platformforge/debate/v1"

# §9 — never a bare "writer"; scope is part of the tier's meaning.
ACCESS_TIERS = ("read-only", "state-writer", "workspace-writer",
                "governed-writer")
# write_scope refines *what* an agent may persist inside the platform:
# runs/artifacts are its own audit trail; "governed" still routes through
# the ops pipeline — no tier mints approval.
WRITE_SCOPES = ("none", "runs", "artifacts", "governed")

# §10 — tiers, not providers. A host adapter maps tier → concrete model.
MODEL_TIERS = ("deterministic", "fast", "standard", "deep",
               "critical-review")

ROLES = ("orchestrator", "planner", "coordinator", "specialist",
         "executor", "reviewer", "critic", "referee", "verifier",
         "guardian")

TASK_STATES = ("draft", "reviewed", "sealed", "rejected", "expired")

# §98 — shared output status vocabulary for every agent-facing document.
OUTPUT_STATUSES = ("confirmed", "supported", "candidate", "unresolved",
                   "refuted", "unsupported", "not-observed")

ROUTING_MODES = ("deterministic", "single-specialist", "multi-specialist",
                 "coordinated", "debate", "critical-review")


class AgentRefusal:
    """§100–101 — the PF-AGENT-* namespace. A refusal keeps its code and
    an `unlock` instruction; it is never a soft failure."""

    NO_EVIDENCE = "PF-AGENT-NO-EVIDENCE"
    BUDGET_EXHAUSTED = "PF-AGENT-BUDGET-EXHAUSTED"
    ROUTE_UNRESOLVED = "PF-AGENT-ROUTE-UNRESOLVED"
    CAPABILITY_UNAVAILABLE = "PF-AGENT-CAPABILITY-UNAVAILABLE"
    INDEPENDENCE_FAILED = "PF-AGENT-INDEPENDENCE-FAILED"
    DEBATE_UNRESOLVED = "PF-AGENT-DEBATE-UNRESOLVED"
    CONTEXT_LIMIT = "PF-AGENT-CONTEXT-LIMIT"
    SPEC_UNSEALED = "PF-AGENT-SPEC-UNSEALED"
    SPEC_REJECTED = "PF-AGENT-SPEC-REJECTED"
    HOST_CAPABILITY = "PF-AGENT-HOST-CAPABILITY"
    SELF_VERIFICATION = "PF-AGENT-SELF-VERIFICATION"
    UNKNOWN_AGENT = "PF-AGENT-UNKNOWN-AGENT"
    ALL = (NO_EVIDENCE, BUDGET_EXHAUSTED, ROUTE_UNRESOLVED,
           CAPABILITY_UNAVAILABLE, INDEPENDENCE_FAILED,
           DEBATE_UNRESOLVED, CONTEXT_LIMIT, SPEC_UNSEALED,
           SPEC_REJECTED, HOST_CAPABILITY, SELF_VERIFICATION,
           UNKNOWN_AGENT)


def refusal(code: str, why: str, unlock: str, **extra: Any) -> dict[str, Any]:
    """Uniform agent refusal — code + reason + unlock, plus context."""
    return {"refusal": code, "why": why, "unlock": unlock, **extra}


def doc_hash(doc: dict[str, Any]) -> str:
    """Content hash over a contract doc (schema field excluded)."""
    body = {k: v for k, v in doc.items() if k != "spec_hash"}
    blob = json.dumps(body, sort_keys=True, default=str)
    return "sha256:" + hashlib.sha256(blob.encode()).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class AgentRunEnvelope:
    """§76 — hard limits for one agentic run. Exhaustion is an explicit
    result (PF-AGENT-BUDGET-EXHAUSTED + partial), never silent success."""

    max_model_calls: int = 8
    max_tool_calls: int = 24
    max_agents: int = 6
    max_fanout: int = 4
    max_context_bytes: int = 120_000
    max_runtime_s: float = 600.0
    max_provider_calls: int = 0

    # measured spend — monotonic, never reset on resume (§141)
    model_calls: int = 0
    tool_calls: int = 0
    agents_used: int = 0
    fanout: int = 0
    context_bytes: int = 0
    provider_calls: int = 0
    elapsed_s: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AgentRunEnvelope:
        return cls(**{k: v for k, v in d.items()
                      if k in cls.__dataclass_fields__})

    def charge(self, *, model_calls: int = 0, tool_calls: int = 0,
               agents: int = 0, fanout: int = 0, context_bytes: int = 0,
               provider_calls: int = 0, elapsed_s: float = 0.0) -> None:
        self.model_calls += model_calls
        self.tool_calls += tool_calls
        self.agents_used += agents
        self.fanout += fanout
        self.context_bytes += context_bytes
        self.provider_calls += provider_calls
        self.elapsed_s += elapsed_s

    def exceeded(self) -> list[str]:
        dims = []
        for limit, spent, name in (
                (self.max_model_calls, self.model_calls, "model_calls"),
                (self.max_tool_calls, self.tool_calls, "tool_calls"),
                (self.max_agents, self.agents_used, "agents"),
                (self.max_fanout, self.fanout, "fanout"),
                (self.max_context_bytes, self.context_bytes,
                 "context_bytes"),
                (self.max_runtime_s, self.elapsed_s, "runtime_s"),
                (self.max_provider_calls, self.provider_calls,
                 "provider_calls")):
            if spent > limit:
                dims.append(f"{name} {spent}>{limit}")
        return dims

    def check(self) -> dict[str, Any] | None:
        """None if inside budget; else the §77/§289 partial-result refusal."""
        over = self.exceeded()
        if not over:
            return None
        return refusal(
            AgentRefusal.BUDGET_EXHAUSTED,
            "run envelope exhausted: " + ", ".join(over),
            "raise the budget class or narrow the task scope and resume "
            "the run — spent budget is preserved, never reset",
            exceeded=over, spent=self.to_dict())


# §112 — budget classes are named envelopes, not magic numbers inline.
BUDGET_CLASSES: dict[str, AgentRunEnvelope] = {
    "tiny": AgentRunEnvelope(max_model_calls=1, max_tool_calls=4,
                             max_agents=1, max_fanout=1,
                             max_context_bytes=24_000, max_runtime_s=60),
    "small": AgentRunEnvelope(max_model_calls=2, max_tool_calls=8,
                              max_agents=2, max_fanout=2,
                              max_context_bytes=48_000, max_runtime_s=120),
    "standard": AgentRunEnvelope(max_model_calls=8, max_tool_calls=24,
                                 max_agents=6, max_fanout=4,
                                 max_context_bytes=120_000,
                                 max_runtime_s=600),
    "deep": AgentRunEnvelope(max_model_calls=16, max_tool_calls=48,
                             max_agents=10, max_fanout=6,
                             max_context_bytes=320_000,
                             max_runtime_s=1800),
    "critical": AgentRunEnvelope(max_model_calls=24, max_tool_calls=64,
                                 max_agents=12, max_fanout=8,
                                 max_context_bytes=480_000,
                                 max_runtime_s=3600),
}


def envelope_for(budget_class: str) -> AgentRunEnvelope:
    """Fresh envelope for a budget class (unknown → standard)."""
    env = BUDGET_CLASSES.get(budget_class) or BUDGET_CLASSES["standard"]
    return AgentRunEnvelope(**{k: getattr(env, k)
                               for k in env.__dataclass_fields__})


@dataclass
class PlatformTaskSpec:
    """§74–75 — sealed task the orchestrator executes. `state` transitions
    only via taskspec.py: draft → reviewed → sealed (or rejected/expired).
    Orchestrators refuse unsealed specs for non-trivial work (§18)."""

    task_id: str
    intent: str
    scope: str = "repo"               # repo | fleet | runtime | change
    domains: tuple[str, ...] = ()
    risk: str = "low"                 # low | medium | high | critical
    complexity: str = "low"           # low | medium | high
    evidence_requirements: tuple[str, ...] = ()
    acceptance_criteria: tuple[str, ...] = ()
    autonomy: str = "read-only"       # read-only | propose | simulate
    allowed_capabilities: tuple[str, ...] = ()
    forbidden_capabilities: tuple[str, ...] = ()
    rollback_requirement: str = "none"     # none | declared | material-bound
    verification_requirement: str = "independent-verifier"
    budget: str = "standard"          # BUDGET_CLASSES key
    state: str = "draft"              # TASK_STATES
    reviewer: str = ""
    review_notes: tuple[str, ...] = ()
    created_at: str = ""
    schema: str = SCHEMA_TASK_SPEC
    spec_hash: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = _now()
        if not self.spec_hash:
            self.spec_hash = doc_hash(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        for k in ("domains", "evidence_requirements",
                  "acceptance_criteria", "allowed_capabilities",
                  "forbidden_capabilities", "review_notes"):
            d[k] = list(d[k])
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PlatformTaskSpec:
        kw = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        for k in ("domains", "evidence_requirements",
                  "acceptance_criteria", "allowed_capabilities",
                  "forbidden_capabilities", "review_notes"):
            if k in kw and isinstance(kw[k], list):
                kw[k] = tuple(kw[k])
        return cls(**kw)

    def transition(self, to: str, reviewer: str = "",
                   notes: tuple[str, ...] = ()) -> PlatformTaskSpec:
        """Move state; returns a NEW spec (specs are immutable docs).
        Legal: draft→reviewed|rejected; reviewed→sealed|rejected;
        any→expired. Everything else refuses."""
        legal = {"draft": {"reviewed", "rejected", "expired"},
                 "reviewed": {"sealed", "rejected", "expired"},
                 "sealed": {"expired"},
                 "rejected": set(), "expired": set()}
        if to not in legal.get(self.state, set()):
            raise ValueError(
                f"illegal TaskSpec transition {self.state}→{to}")
        d = self.to_dict()
        d["state"] = to
        d["reviewer"] = reviewer or self.reviewer
        d["review_notes"] = list(notes) or list(self.review_notes)
        d["spec_hash"] = ""
        out = PlatformTaskSpec.from_dict(d)
        return out


@dataclass
class AgentHandoff:
    """§71–73 — every transfer between agents is structured and carries
    refs (artifact/fact/graph/context-pack), never raw context bodies."""

    sender: str                     # serialized as `from`
    to: str
    task_id: str
    reason: str = ""
    completed: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()          # fact_id / artifact refs only
    findings: tuple[str, ...] = ()          # finding ids / summaries
    open_questions: tuple[str, ...] = ()
    unresolved: tuple[str, ...] = ()
    budget_spent: dict[str, Any] = field(default_factory=dict)
    budget_remaining: dict[str, Any] = field(default_factory=dict)
    next_required_capability: str = ""
    context_pack_ref: str = ""              # §73 — pack hash, not body
    schema: str = SCHEMA_HANDOFF

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["from"] = d.pop("sender")
        for k in ("completed", "evidence", "findings", "open_questions",
                  "unresolved"):
            d[k] = list(d[k])
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AgentHandoff:
        kw = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        if "from" in d:
            kw["sender"] = d["from"]
        for k in ("completed", "evidence", "findings", "open_questions",
                  "unresolved"):
            if k in kw and isinstance(kw[k], list):
                kw[k] = tuple(kw[k])
        return cls(**kw)


@dataclass
class AgentRunRecord:
    """§138–139 — the auditable receipt of one agentic run. Persisted
    under .platformforge/runs/ (append-only)."""

    run_id: str
    task_spec_hash: str
    router_decision: dict[str, Any] = field(default_factory=dict)
    agents: tuple[str, ...] = ()
    handoffs: tuple[dict[str, Any], ...] = ()
    budget: dict[str, Any] = field(default_factory=dict)
    evidence: tuple[str, ...] = ()
    debates: tuple[str, ...] = ()
    gates: tuple[str, ...] = ()
    verifier: str = ""
    verdict: str = "unresolved"             # OUTPUT_STATUSES
    checkpoint: dict[str, Any] = field(default_factory=dict)
    started_at: str = ""
    finished_at: str = ""
    schema: str = SCHEMA_RUN

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        for k in ("agents", "handoffs", "evidence", "debates", "gates"):
            d[k] = list(d[k])
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AgentRunRecord:
        kw = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        for k in ("agents", "evidence", "debates", "gates"):
            if k in kw and isinstance(kw[k], list):
                kw[k] = tuple(kw[k])
        if isinstance(kw.get("handoffs"), list):
            kw["handoffs"] = tuple(kw["handoffs"])
        return cls(**kw)


@dataclass
class DebatePosition:
    """One participant's position — must cite evidence (§130–131)."""
    agent: str
    claim: str
    evidence: tuple[str, ...] = ()
    evidence_tier: int = 7
    freshness: str = "unresolved"
    round: int = 0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["evidence"] = list(self.evidence)
        return d


@dataclass
class Debate:
    """§126–129 — bounded disagreement. Default shape is small:
    2 specialists + 1 critic + 1 referee, 1–3 rounds, inside the run
    envelope. A position without evidence is refused, not debated."""

    debate_id: str
    question: str
    positions: tuple[DebatePosition, ...] = ()
    max_participants: int = 4
    max_rounds: int = 3
    round: int = 0
    outcome: str = "open"            # open | winner | tied | unresolved
    winner: str = ""
    axes: tuple[str, ...] = ()
    receipt: dict[str, Any] = field(default_factory=dict)
    schema: str = SCHEMA_DEBATE

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["positions"] = [p.to_dict() for p in self.positions]
        d["axes"] = list(self.axes)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Debate:
        kw = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        kw["positions"] = tuple(
            DebatePosition(**{k: v for k, v in p.items()
                              if k in DebatePosition.__dataclass_fields__})
            for p in d.get("positions", []))
        if isinstance(kw.get("axes"), list):
            kw["axes"] = tuple(kw["axes"])
        return cls(**kw)
