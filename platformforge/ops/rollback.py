"""Cycle 4.1 — rollback planning v2 (§21–43).

A `rollback_action` name alone is not a rollback. Correct reversal =
forward intent + captured pre-state + execution result + strategy.
`RollbackPlan` now carries a per-step strategy, the material hashes it
depends on, and an honest `status`:

    executable        — typed actions validated, material complete
    requires-replan   — reversal needs a NEW governed plan (terraform)
    manual-only       — human procedure required
    impossible        — factually cannot be undone
    unresolved        — insufficient evidence to claim any of the above

"rollback ready" is only ever said when status == executable (§37).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from platformforge.live.models import now_iso
from platformforge.ops.actions import spec_for, validate_action
from platformforge.ops.rollback_builders import BUILDERS

ROLLBACK_SCHEMA = "platformforge/rollback-plan/v2"

STRATEGIES = ("direct-inverse", "source-revert", "previous-revision",
              "compensating-operation", "replan-required",
              "manual-only", "impossible", "unknown")

# legacy v1 strategy names → v2 (envelopes persisted before 4.1)
LEGACY_STRATEGY = {
    "git-revert": "direct-inverse",
    "terraform-revert": "replan-required",
    "previous-artifact": "previous-revision",
    "argo-rollback": "previous-revision",
    "rollout-undo": "previous-revision",
    "compensating": "compensating-operation",
    "manual-only": "manual-only",
    "impossible": "impossible",
    "unknown": "unknown",
}

STATUSES = ("executable", "requires-replan", "manual-only",
            "impossible", "unresolved")

TRIGGERS = ("verification-failed", "slo-regression", "manual",
            "policy-revocation", "incident")

# worst-first rollup across steps
_SEVERITY = {"impossible": 5, "unknown": 4, "manual-only": 3,
             "replan-required": 2}


@dataclass
class RollbackPlan:
    rollback_id: str = ""
    trigger: str = "verification-failed"
    strategy: str = "unknown"            # worst-of step strategies
    status: str = "unresolved"           # §36
    steps: list[dict[str, Any]] = field(default_factory=list)
    actions: list[dict[str, Any]] = field(default_factory=list)  # executable
    material_hashes: list[str] = field(default_factory=list)
    replans: list[dict[str, Any]] = field(default_factory=list)
    preconditions: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    data_impact: str = "unknown"
    expected_delta: dict[str, Any] = field(default_factory=dict)
    automatic: bool = False              # §38–39 — lab/non-prod only

    def validate(self) -> list[dict[str, Any]]:
        v = []
        if self.strategy not in STRATEGIES:
            v.append({"refusal": "PF-OPS-BAD-ROLLBACK-TYPE",
                      "unlock": f"strategy in {STRATEGIES}"})
        if self.status not in STATUSES:
            v.append({"refusal": "PF-OPS-BAD-ROLLBACK-STATUS",
                      "unlock": f"status in {STATUSES}"})
        if self.status in ("manual-only", "impossible", "unresolved",
                           "requires-replan") and self.automatic:
            v.append({"refusal": "PF-OPS-ROLLBACK-CONTRADICTION",
                      "unlock": "only status=executable may be "
                                "automatic (§38)"})
        # §35 — every executable action must pass typed validation
        for a in self.actions:
            bad = validate_action(a.get("action", ""),
                                  a.get("params", {}))
            if bad:
                v.append(bad)
        return v

    def to_dict(self) -> dict[str, Any]:
        return {"schema": ROLLBACK_SCHEMA, "rollback_id": self.rollback_id,
                "trigger": self.trigger, "strategy": self.strategy,
                "status": self.status, "steps": self.steps,
                "actions": self.actions,
                "material_hashes": self.material_hashes,
                "replans": self.replans,
                "preconditions": self.preconditions,
                "limitations": self.limitations,
                "data_impact": self.data_impact,
                "expected_delta": self.expected_delta,
                "automatic": self.automatic,
                "created_at": now_iso()}


def _status_rollup(step_statuses: list[str]) -> str:
    if not step_statuses:
        return "unresolved"
    if "impossible" in step_statuses:
        return "impossible"
    if "unresolved" in step_statuses:
        return "unresolved"
    if "manual-only" in step_statuses:
        return "manual-only"
    if "requires-replan" in step_statuses:
        return "requires-replan"
    return "executable"


def _strategy_rollup(strategies: set[str]) -> str:
    if not strategies:
        return "unknown"
    worst = max(strategies,
                key=lambda s: _SEVERITY.get(s, 1))
    if len(strategies) > 1 and _SEVERITY.get(worst, 0) == 0:
        return "compensating-operation"   # mixed executable → saga
    return worst


def build_rollback_plan(steps: list[dict[str, Any]],
                        materials: dict[str, Any] | None = None,
                        context: dict[str, Any] | None = None
                        ) -> RollbackPlan:
    """§30 pipeline — ActionSpec contract + captured materials → plan.

    `steps`: forward steps [{step_id, action, params}].
    `materials`: {step_id: RollbackMaterial|dict} captured pre/during
    forward execution (empty at plan-time → honest degraded status).
    """
    ctx = context or {}
    materials = materials or {}
    plan = RollbackPlan()
    strategies: set[str] = set()
    statuses: list[str] = []
    for s in steps:
        act = s.get("action", "")
        spec = spec_for(act)
        mat = materials.get(s.get("step_id"))
        mat_d = (mat.to_dict() if hasattr(mat, "to_dict")
                 else dict(mat or {}))
        if spec is None:
            strategies.add("unknown")
            statuses.append("unresolved")
            plan.limitations.append(f"{act}: not a typed action")
            continue
        st_strategy = spec.rollback_strategy
        strategies.add(st_strategy)
        step_rec = {"step_id": s.get("step_id"), "action": act,
                    "strategy": st_strategy,
                    "material_hash": mat_d.get("hash")}
        if mat_d.get("hash"):
            plan.material_hashes.append(mat_d["hash"])
        missing = [k for k in spec.pre_state_requirements
                   if k not in mat_d.get("pre_state", {})]
        if st_strategy in ("manual-only", "impossible", "unknown"):
            statuses.append(
                "manual-only" if st_strategy == "manual-only"
                else "impossible" if st_strategy == "impossible"
                else "unresolved")
            step_rec["status"] = statuses[-1]
        elif st_strategy == "replan-required":
            statuses.append("requires-replan")
            step_rec["status"] = "requires-replan"
            builder = BUILDERS.get(spec.rollback_builder)
            if builder:
                out = builder(s.get("params", {}), mat_d, ctx) or {}
                if out.get("replan"):
                    plan.replans.append({**out["replan"],
                                         "step_id": s.get("step_id"),
                                         "action": act})
        elif missing:
            statuses.append("unresolved")
            step_rec["status"] = "unresolved"
            step_rec["missing_pre_state"] = missing
            plan.limitations.append(
                f"{act}: missing pre-state {missing} — strategy "
                f"{st_strategy} not executable (§31)")
        else:
            builder = BUILDERS.get(spec.rollback_builder)
            out = builder(s.get("params", {}), mat_d, ctx) \
                if builder else None
            if out and out.get("action"):
                bad = validate_action(out["action"],
                                      out.get("params", {}))
                if bad:
                    statuses.append("unresolved")
                    step_rec["status"] = "unresolved"
                    plan.limitations.append(
                        f"{act}: built rollback failed validation — "
                        f"{bad['refusal']}")
                else:
                    statuses.append("executable")
                    step_rec["status"] = "executable"
                    step_rec["rollback_action"] = out["action"]
                    step_rec["rationale"] = out.get("rationale", "")
                    plan.actions.append(
                        {"action": out["action"],
                         "params": out["params"],
                         "compensates": s.get("step_id"),
                         "material_hash": mat_d.get("hash")})
            else:
                statuses.append("unresolved")
                step_rec["status"] = "unresolved"
                plan.limitations.append(
                    f"{act}: builder returned no action — material "
                    "insufficient")
        plan.steps.append(step_rec)

    plan.strategy = _strategy_rollup(strategies)
    plan.status = _status_rollup(statuses)
    # §38–39 — auto-rollback: executable + non-prod + explicitly allowed
    plan.automatic = bool(ctx.get("automatic_allowed")) and \
        plan.status == "executable"
    if ctx.get("environment") in ("prod", "production") and \
            plan.automatic:
        plan.automatic = False
        plan.limitations.append("auto-rollback disabled for prod (§39)")
    elif plan.automatic:
        plan.limitations.append("auto-rollback allowed only in lab/"
                                "non-prod (§38–39)")
    return plan


def terraform_plan_reuse_check(forward_plan_hash: str,
                               rollback_plan_hash: str
                               ) -> dict[str, Any] | None:
    """§18 invariant — a saved forward plan is never a rollback plan."""
    if forward_plan_hash and forward_plan_hash == rollback_plan_hash:
        return {"refusal": "PF-OPS-PLAN-REUSE",
                "unlock": "rollback via terraform must plan against "
                          "reverted source — never reuse the forward "
                          "saved plan"}
    return None


# --- backward-compat -----------------------------------------------------

def derive_rollback(actions: list[dict[str, Any]],
                    context: dict[str, Any] | None = None) -> RollbackPlan:
    """Plan-time derivation (no materials yet): declares per-step
    strategies + capture requirements. Status stays `unresolved`
    until materials exist — never claims executable early."""
    steps = [{"step_id": a.get("step_id", f"s{i}"),
              "action": a.get("action", ""),
              "params": a.get("params", {})}
             for i, a in enumerate(actions)]
    return build_rollback_plan(steps, materials=None, context=context)


def compensate_for(steps: list[dict[str, Any]],
                   materials: dict[str, Any] | None = None,
                   ) -> dict[str, Any]:
    """§105–106 — saga compensation for *completed* forward steps,
    reverse order, built from materials (not forward params)."""
    comp: list[dict[str, Any]] = []
    manual: list[str] = []
    mats = materials or {}
    for s in reversed(steps):
        if s.get("status") != "completed":
            continue
        spec = spec_for(s.get("action", ""))
        mat = mats.get(s.get("step_id"))
        mat_d = (mat.to_dict() if hasattr(mat, "to_dict")
                 else dict(mat or {}))
        out = None
        if spec and spec.rollback_builder in BUILDERS:
            out = BUILDERS[spec.rollback_builder](
                s.get("params", {}), mat_d, {})
        if out and out.get("action"):
            comp.append({"action": out["action"],
                         "params": out["params"],
                         "compensates": s.get("step_id")})
        else:
            manual.append(s.get("step_id", "?"))
    return {"compensating_actions": comp, "manual_steps": manual}
