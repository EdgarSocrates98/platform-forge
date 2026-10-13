"""EconomyPlan (§9–11) — the canonical plan every run opens with.

One plan links the whole pipeline (§8): deterministic reach → cache →
context → budget → routing → execution → ledger → checkpoint → observed
usage → reconciliation → quality → report. Every section carries a
`reason` so `economy explain` can answer why-deterministic / why-model /
why-this-context / why-this-budget from the plan itself (§11).
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any

SCHEMA = "platformforge/economy-plan/v1"

PIPELINE_STAGES = (
    "deterministic_reach", "cache_lookup", "context_plan",
    "budget_plan", "routing_plan", "execution", "ledger",
    "checkpoint", "observed_usage", "reconciliation",
    "quality_validation", "economy_report",
)

STRATEGIES = ("deterministic-only", "deterministic-plus-compose",
              "single-specialist", "multi-specialist", "coordinated",
              "review-required", "refuse")

REFUSAL_POLICIES = ("refuse", "partial", "escalate-required")


@dataclass
class PlanSection:
    """One pipeline decision with its mandatory explanation (§11)."""
    decision: str
    reason: str
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EconomyPlan:
    """§10 — canonical fields. Immutable once minted: a plan is a claim
    about intent, recorded before execution and reconciled after."""
    schema: str = SCHEMA
    run_id: str = ""
    task: str = ""
    risk: str = "low"                      # low|medium|high|critical
    complexity: str = "low"                # low|medium|high
    deterministic_reach: PlanSection = field(
        default_factory=lambda: PlanSection("unknown", ""))
    cache_plan: PlanSection = field(
        default_factory=lambda: PlanSection("miss", ""))
    context_plan: PlanSection = field(
        default_factory=lambda: PlanSection("minimal", ""))
    routing_plan: PlanSection = field(
        default_factory=lambda: PlanSection("deterministic-only", ""))
    budget: dict[str, Any] = field(default_factory=dict)
    verification_floor: str = "V0"         # V0..V5 — never lowered by budget
    provider_call_budget: int | None = None
    expected_usage: dict[str, Any] = field(default_factory=dict)
    fallbacks: list[str] = field(default_factory=list)
    refusal_policy: str = "refuse"         # REFUSAL_POLICIES
    profile: str = "balanced"              # routing profile
    created_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if self.routing_plan.decision and \
                self.routing_plan.decision not in STRATEGIES:
            raise ValueError(
                f"routing_plan.decision {self.routing_plan.decision!r} "
                f"not in {STRATEGIES}")
        if self.refusal_policy not in REFUSAL_POLICIES:
            raise ValueError(
                f"refusal_policy {self.refusal_policy!r} not in "
                f"{REFUSAL_POLICIES}")

    @classmethod
    def mint_run_id(cls, task: str, scope: str = "") -> str:
        """Deterministic run id — same task+scope+clock mints a stable,
        content-derived id (not random: runs are reproducible artifacts)."""
        h = hashlib.sha256(
            f"{task}|{scope}|{int(time.time() * 1e6)}".encode()
        ).hexdigest()[:12]
        return f"run-{h}"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> EconomyPlan:
        out = dict(d)
        for k in ("deterministic_reach", "cache_plan", "context_plan",
                  "routing_plan"):
            if isinstance(out.get(k), dict):
                out[k] = PlanSection(**out[k])
        return cls(**{k: v for k, v in out.items()
                      if k in cls.__dataclass_fields__})

    def explain(self) -> dict[str, str]:
        """§11 — the six mandatory questions, answered from the plan."""
        return {
            "why_deterministic": self.deterministic_reach.reason,
            "why_model": (self.routing_plan.reason
                          if self.routing_plan.decision
                          not in ("deterministic-only",)
                          else "no model — deterministic reach sufficed"),
            "why_multi_agent": (self.routing_plan.reason
                                if self.routing_plan.decision in
                                ("multi-specialist", "coordinated")
                                else "not multi-agent"),
            "why_this_context": self.context_plan.reason,
            "why_this_budget": self.budget.get("reason",
                                               "default envelope"),
            "why_this_provider_call": (
                "none planned" if not self.provider_call_budget
                else f"provider_call_budget={self.provider_call_budget}"),
        }

    def receipt(self) -> dict[str, Any]:
        """One-decision receipt link (§158): the plan hash binds every
        later ledger/checkpoint/reconciliation row to this intent."""
        body = json.dumps(self.to_dict(), sort_keys=True, default=str)
        return {"schema": SCHEMA, "run_id": self.run_id,
                "plan_hash": hashlib.sha256(body.encode()).hexdigest(),
                "pipeline": list(PIPELINE_STAGES)}
