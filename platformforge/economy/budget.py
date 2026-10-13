"""BudgetEnvelope (§12–24) — the canonical spend contract.

Eleven dimensions (§13), each with an independent soft/hard limit
(§14–16). A hard-limit overrun is never silent — the verdict carries
PF-ECONOMY-BUDGET-EXHAUSTED plus the action the caller must take
(§17–18). `protected_items` name what a reduce-scope action may never
drop (§19); VERIFY/SECURITY/CONTRACT phases cannot be budget-removed
(§23).

The envelope is the single contract — TokenSave's `check_input_budget`
implements the context dimension's reduce/refuse/escalate detail; the
envelope is where every dimension (incl. provider calls, fanout,
wall time, money) is governed together.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any

SCHEMA = "platformforge/budget-envelope/v1"

DIMENSIONS = ("context_bytes", "input_tokens", "output_tokens",
              "model_calls", "tool_calls", "provider_calls", "agents",
              "fanout", "parallelism", "wall_time", "money")

# §21/§22 — pipeline phases + the SDD phases they map to.
PHASES = ("discover", "analyze", "review", "debate", "verify", "report")
SDD_PHASES = ("DISCOVER", "DEFINE", "DESIGN", "CONTRACT", "PLAN",
              "BUILD", "REVIEW", "VERIFY", "SHIP")
PROTECTED_PHASES = ("VERIFY", "SECURITY", "CONTRACT")  # §23

ROLES = ("specialist", "reviewer", "critic", "referee", "verifier")

# §19 — reduce-scope may never drop these.
PROTECTED_ITEMS = ("critical_evidence", "unresolved_markers",
                   "security_findings", "policy_failures",
                   "rollback_info", "acceptance_criteria")

# §18 — what a run does when budget is insufficient.
ACTIONS = ("reduce_scope", "reuse_cache", "switch_deterministic",
           "request_escalation", "return_partial", "refuse")

EXHAUSTED = "PF-ECONOMY-BUDGET-EXHAUSTED"


@dataclass
class Limit:
    """soft = target (may escalate via policy); hard = never exceeded."""
    soft: float | None = None
    hard: float | None = None

    @classmethod
    def from_dict(cls, d: Any) -> Limit:
        if isinstance(d, (int, float)):
            return cls(hard=float(d))
        return cls(soft=d.get("soft"), hard=d.get("hard"))

    def to_dict(self) -> dict[str, Any]:
        return {"soft": self.soft, "hard": self.hard}


@dataclass
class BudgetVerdict:
    decision: str                  # ok|soft_exceeded|hard_exceeded
    dimension: str = ""
    spent: float = 0.0
    limit: float | None = None
    action: str = ""               # §18 action for the caller
    code: str = ""
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BudgetEnvelope:
    """§12 — canonical contract. `limits` keys ⊆ DIMENSIONS."""
    schema: str = SCHEMA
    limits: dict[str, Limit] = field(default_factory=dict)
    phase_budgets: dict[str, dict[str, Limit]] = field(default_factory=dict)
    role_budgets: dict[str, dict[str, Limit]] = field(default_factory=dict)
    protected_items: list[str] = field(
        default_factory=lambda: list(PROTECTED_ITEMS))
    overrun_action: str = "refuse"     # §18 default
    soft_policy: str = "warn"          # warn|escalate — soft may be crossed
    created_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        bad = set(self.limits) - set(DIMENSIONS)
        if bad:
            raise ValueError(f"unknown budget dimensions {sorted(bad)}")
        for p in self.phase_budgets:
            if p not in PHASES and p not in SDD_PHASES:
                raise ValueError(f"unknown phase {p!r}")
            bad = set(self.phase_budgets[p]) - set(DIMENSIONS)
            if bad:
                raise ValueError(f"phase {p}: unknown dims {sorted(bad)}")
        for r in self.role_budgets:
            if r not in ROLES:
                raise ValueError(f"unknown role {r!r}")
            bad = set(self.role_budgets[r]) - set(DIMENSIONS)
            if bad:
                raise ValueError(f"role {r}: unknown dims {sorted(bad)}")
        bad = set(self.protected_items) - set(PROTECTED_ITEMS)
        if bad:
            raise ValueError(
                f"protected_items not in {PROTECTED_ITEMS}: {sorted(bad)}")
        if self.overrun_action not in ACTIONS:
            raise ValueError(
                f"overrun_action {self.overrun_action!r} not in {ACTIONS}")

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> BudgetEnvelope:
        out = dict(d)
        out["limits"] = {k: Limit.from_dict(v)
                         for k, v in out.get("limits", {}).items()}
        for grp in ("phase_budgets", "role_budgets"):
            out[grp] = {k: {dk: Limit.from_dict(dv)
                            for dk, dv in v.items()}
                        for k, v in out.get(grp, {}).items()}
        return cls(**{k: v for k, v in out.items()
                      if k in cls.__dataclass_fields__})

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["limits"] = {k: v.to_dict() for k, v in self.limits.items()}
        d["phase_budgets"] = {p: {k: v.to_dict() for k, v in lim.items()}
                              for p, lim in self.phase_budgets.items()}
        d["role_budgets"] = {r: {k: v.to_dict() for k, v in lim.items()}
                             for r, lim in self.role_budgets.items()}
        return d

    def _effective(self, dimension: str, phase: str = "",
                   role: str = "") -> Limit:
        """Narrowest applicable limit: role > phase > envelope default."""
        cand = [self.limits.get(dimension, Limit())]
        if phase and phase in self.phase_budgets and \
                dimension in self.phase_budgets[phase]:
            cand.append(self.phase_budgets[phase][dimension])
        if role and role in self.role_budgets and \
                dimension in self.role_budgets[role]:
            cand.append(self.role_budgets[role][dimension])
        soft = min((c.soft for c in cand if c.soft is not None),
                   default=None)
        hard = min((c.hard for c in cand if c.hard is not None),
                   default=None)
        return Limit(soft=soft, hard=hard)

    def check(self, dimension: str, proposed_spend: float,
              *, phase: str = "", role: str = "") -> BudgetVerdict:
        """§15–17 — hard is never exceeded; soft crosses with a verdict,
        never silently."""
        lim = self._effective(dimension, phase, role)
        if lim.hard is not None and proposed_spend > lim.hard:
            return BudgetVerdict(
                "hard_exceeded", dimension, proposed_spend, lim.hard,
                action=self.overrun_action, code=EXHAUSTED,
                detail=f"{dimension} hard limit {lim.hard} "
                       f"< proposed {proposed_spend}; action="
                       f"{self.overrun_action}")
        if lim.soft is not None and proposed_spend > lim.soft:
            return BudgetVerdict(
                "soft_exceeded", dimension, proposed_spend, lim.soft,
                action=self.soft_policy,
                detail=f"{dimension} soft limit {lim.soft} exceeded "
                       f"(policy={self.soft_policy})")
        return BudgetVerdict("ok", dimension, proposed_spend,
                             lim.hard if lim.hard is not None else lim.soft)

    def reducible(self, item: str) -> bool:
        """§19 — protected items are never droppable for savings."""
        return item not in self.protected_items

    def phase_removable(self, phase: str) -> bool:
        """§23 — protected phases cannot be removed for cost."""
        return phase.upper() not in PROTECTED_PHASES


DEFAULT_PHASE_SPLIT = {
    "DISCOVER": 0.15, "DEFINE": 0.10, "DESIGN": 0.15, "CONTRACT": 0.05,
    "PLAN": 0.10, "BUILD": 0.15, "REVIEW": 0.10, "VERIFY": 0.15,
    "SHIP": 0.05,
}


def phase_budgets(total: float, dimension: str = "input_tokens",
                  split: dict[str, float] | None = None
                  ) -> dict[str, dict[str, Limit]]:
    """§22 — split a dimension total across SDD phases; protected phases
    keep their floor and are never zeroed by this helper."""
    split = split or DEFAULT_PHASE_SPLIT
    out: dict[str, dict[str, Limit]] = {}
    for phase, frac in split.items():
        out[phase] = {dimension: Limit(soft=round(total * frac, 3))}
    return out
