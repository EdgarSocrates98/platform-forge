"""Cycle 4 — rollback planning + compensation (§119–127, ADR-0029).

Rollback is *preplanned*: every R3+ operation evaluates a RollbackPlan
before execution. Types map to real mechanisms (git revert, terraform
revert, previous artifact, argo rollback, rollout undo, compensating
operation). `manual-only` and `impossible` are honest outcomes — unknown
rollback raises risk and blocks autonomy; it is never invented.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from platformforge.live.models import now_iso
from platformforge.ops.actions import spec_for

ROLLBACK_SCHEMA = "platformforge/rollback-plan/v1"
ROLLBACK_TYPES = ("git-revert", "terraform-revert", "previous-artifact",
                  "argo-rollback", "rollout-undo", "compensating",
                  "manual-only", "impossible", "unknown")
TRIGGERS = ("verification-failed", "slo-regression", "manual",
            "policy-revocation", "incident")


@dataclass
class RollbackPlan:
    rollback_id: str = ""
    trigger: str = "verification-failed"
    strategy: str = "unknown"        # ROLLBACK_TYPES
    actions: list[dict[str, Any]] = field(default_factory=list)
    preconditions: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    data_impact: str = "unknown"
    expected_delta: dict[str, Any] = field(default_factory=dict)
    automatic: bool = False          # §123 — lab/non-prod only

    def validate(self) -> list[dict[str, Any]]:
        v = []
        if self.strategy not in ROLLBACK_TYPES:
            v.append({"refusal": "PF-OPS-BAD-ROLLBACK-TYPE",
                      "unlock": f"strategy in {ROLLBACK_TYPES}"})
        if self.strategy in ("manual-only", "impossible") and \
                self.automatic:
            v.append({"refusal": "PF-OPS-ROLLBACK-CONTRADICTION",
                      "unlock": "manual-only/impossible rollback cannot "
                                "be automatic"})
        if self.strategy == "unknown":
            v.append({"refusal": "PF-OPS-ROLLBACK-UNKNOWN",
                      "unlock": "declare a rollback strategy or accept "
                                "elevated risk — unknown ≠ safe"})
        for a in self.actions:
            if spec_for(a.get("action", "")) is None:
                v.append({"refusal": "PF-OPS-UNKNOWN-ACTION",
                          "unlock": f"rollback action {a.get('action')} "
                                    "not in vocabulary"})
        return v

    def to_dict(self) -> dict[str, Any]:
        return {"schema": ROLLBACK_SCHEMA, "rollback_id": self.rollback_id,
                "trigger": self.trigger, "strategy": self.strategy,
                "actions": self.actions, "preconditions": self.preconditions,
                "limitations": self.limitations,
                "data_impact": self.data_impact,
                "expected_delta": self.expected_delta,
                "automatic": self.automatic,
                "created_at": now_iso()}


# --- strategy selection -------------------------------------------------

_STRATEGY_BY_ACTION = {
    "git.open_pr": "git-revert", "git.commit": "git-revert",
    "git.apply_patch": "git-revert",
    "terraform.apply_saved_plan": "terraform-revert",
    "tofu.apply_saved_plan": "terraform-revert",
    "argocd.sync": "argo-rollback",
    "kubernetes.scale": "previous-artifact",
    "kubernetes.rollout_restart": "rollout-undo",
    "kubernetes.annotate": "compensating",
}


def derive_rollback(actions: list[dict[str, Any]],
                    context: dict[str, Any] | None = None) -> RollbackPlan:
    """Derive the rollback plan from the forward typed actions —
    each action's `rollback_action` from the vocabulary or an honest
    manual-only/impossible when no inverse exists."""
    ctx = context or {}
    plan = RollbackPlan()
    strategies: set[str] = set()
    for a in actions:
        act = a.get("action", "")
        spec = spec_for(act)
        st = _STRATEGY_BY_ACTION.get(act, "compensating")
        if spec is not None and spec.rollback_action:
            inv = dict(a.get("params", {}))
            if act == "kubernetes.scale":
                inv["replicas"] = ctx.get("previous_replicas",
                                          inv.get("replicas"))
            plan.actions.append({"action": spec.rollback_action,
                                 "params": inv})
            strategies.add(st)
        elif spec is not None:
            strategies.add("compensating")
            plan.limitations.append(f"{act}: no typed inverse — "
                                    "compensating operation required")
        else:
            strategies.add("unknown")
    if "unknown" in strategies:
        plan.strategy = "unknown"
    elif "compensating" in strategies:
        plan.strategy = "compensating"
    elif len(strategies) == 1:
        plan.strategy = strategies.pop()
    elif strategies:
        plan.strategy = "compensating"   # mixed → saga-style compensation
    else:
        plan.strategy = "unknown"
    plan.automatic = bool(ctx.get("automatic_allowed"))
    if ctx.get("environment") == "prod" and plan.automatic:
        plan.automatic = False
        plan.limitations.append("auto-rollback disabled for prod (§124)")
    elif plan.automatic:
        plan.limitations.append("auto-rollback allowed only in lab/"
                                "non-prod (§123–124)")
    return plan


def compensate_for(steps: list[dict[str, Any]]
                   ) -> list[dict[str, Any]]:
    """§105–106 — saga compensation: inverse actions in reverse order
    for completed steps; steps without inverses become manual tasks."""
    comp: list[dict[str, Any]] = []
    manual: list[str] = []
    for s in reversed(steps):
        if s.get("status") != "completed":
            continue
        spec = spec_for(s.get("action", ""))
        if spec and spec.rollback_action:
            comp.append({"action": spec.rollback_action,
                         "params": dict(s.get("params", {})),
                         "compensates": s.get("step_id")})
        else:
            manual.append(s.get("step_id", "?"))
    return {"compensating_actions": comp, "manual_steps": manual}
