"""Cycle 4 — operations orchestrator.

Drives the §8 pipeline end to end with *no implicit skips*:

    intent → plan → simulate → risk → policy → approval →
    envelope → preconditions → execute (typed) → verify →
    converge | rollback → ledger receipts

Every stage emits receipts into the OperationLedger; every refusal is a
`PF-OPS-*` object. Executors run only via injected host transports —
`dry_run` is the default and `--execute` semantics live in the CLI.
"""

from __future__ import annotations

from typing import Any

from platformforge.ops.actions import spec_for
from platformforge.ops.approval import Approval, BreakGlass, check_approval
from platformforge.ops.envelope import ExecutionEnvelope
from platformforge.ops.models import ChangeIntent, ChangePlan, PlanStep
from platformforge.ops.operation import ExecutionStep, LockTable, Operation, OperationLedger
from platformforge.ops.policy import Policy, evaluate
from platformforge.ops.preconditions import check_preconditions
from platformforge.ops.risk import assess, classify_reversibility
from platformforge.ops.rollback import RollbackPlan, derive_rollback
from platformforge.ops.source_of_truth import resolve


def executor_for(action: str):
    from platformforge.ops.executors.base import ObserveExecutor
    from platformforge.ops.executors.git import GitExecutor
    from platformforge.ops.executors.gitops import ArgoCDExecutor, KubernetesExecutor
    from platformforge.ops.executors.terraform import TerraformExecutor, TofuExecutor
    mapping = {"git": GitExecutor, "terraform": TerraformExecutor,
               "tofu": TofuExecutor, "argocd": ArgoCDExecutor,
               "kubernetes": KubernetesExecutor, "observe": ObserveExecutor}
    spec = spec_for(action)
    cls = mapping.get(spec.executor if spec else "")
    return cls() if cls else None


def propose(intent: ChangeIntent,
            resources: list[dict[str, Any]] | None = None,
            sot_context: dict[str, Any] | None = None
            ) -> dict[str, Any]:
    """§8 stage 1-3: validate intent, resolve source of truth."""
    violations = intent.validate()
    if violations:
        return {"ok": False, "refusals": violations}
    resolutions = resolve(resources or [], sot_context)
    unresolved = [r.to_dict() for r in resolutions if not r.resolved]
    return {"ok": True, "intent": intent.to_dict(),
            "resolutions": [r.to_dict() for r in resolutions],
            "unresolved_sources": unresolved,
            "requires_human_review": bool(unresolved)}


def plan(intent: ChangeIntent, *,
         plan_id: str = "",
         steps: list[PlanStep] | None = None,
         expected_delta=None,
         affected: list[str] | None = None) -> ChangePlan:
    p = ChangePlan(plan_id=plan_id or f"plan-{intent.intent_id}",
                   intent_id=intent.intent_id,
                   steps=list(steps or []),
                   affected_resources=list(affected
                                           or intent.target_resources),
                   expected_delta=expected_delta
                   or __import__("platformforge.ops.models",
                                 fromlist=["ExpectedDelta"]).ExpectedDelta())
    return p


def assess_risk(plan: ChangePlan, context: dict[str, Any] | None = None
                ) -> dict[str, Any]:
    """Per-step risk assessments + plan ceiling (max class wins)."""
    ctx = context or {}
    per_step = []
    worst = "R0"
    from platformforge.ops.risk import RISK_RANK
    for s in plan.steps:
        rev = classify_reversibility(s.action, s.params, ctx)
        a = assess(s.action, s.params, {**ctx, "reversibility": rev})
        per_step.append({"step_id": s.step_id, "action": s.action,
                         **a.to_dict()})
        if RISK_RANK[a.risk_class] > RISK_RANK[worst]:
            worst = a.risk_class
    return {"plan_id": plan.plan_id, "risk_class": worst,
            "steps": per_step}


def decide(plan: ChangePlan, policies: list[Policy],
           inp: dict[str, Any] | None = None,
           exceptions=None, at: str | None = None):
    base_inp = {"plan_id": plan.plan_id, "plan_hash": plan.hash(),
                "intent_id": plan.intent_id,
                "environment": (inp or {}).get("environment", "unknown"),
                **(inp or {})}
    return evaluate(base_inp, policies, exceptions=exceptions, at=at)


def mint_envelope(plan: ChangePlan, *, execution_id: str,
                  decisions: list, approvals: list[Approval],
                  risk: dict[str, Any], rollback: RollbackPlan | None,
                  preconditions: dict[str, Any] | None = None,
                  verification: dict[str, Any] | None = None,
                  expires_at: str = ""
                  ) -> ExecutionEnvelope | dict[str, Any]:
    """Envelopes mint only when every decision allows/requires-satisfied
    — never self-minted."""
    if not decisions:
        return {"refusal": "PF-OPS-ENVELOPE-UNGOVERNED",
                "unlock": "run policy evaluation first"}
    for d in decisions:
        eff = d.effective
        if eff in ("deny", "would_deny", "unresolved"):
            return {"refusal": "PF-OPS-POLICY-BLOCK",
                    "unlock": f"policy {d.policy_id} → {eff}; resolve "
                              "before minting an envelope"}
    actions = [{"step_id": s.step_id, "action": s.action,
                "params": s.params} for s in plan.steps]
    env = ExecutionEnvelope(
        execution_id=execution_id, intent_id=plan.intent_id,
        change_plan_hash=plan.hash(),
        executor=_dominant_executor(plan),
        actions=actions, scope=list(plan.affected_resources),
        preconditions=preconditions or {},
        policy_decisions=[d.to_dict() for d in decisions],
        approvals=[a.approval_id for a in approvals],
        risk=risk, expected_delta=plan.expected_delta.to_dict(),
        verification=verification or {},
        rollback=(rollback or derive_rollback(actions)).to_dict(),
        expires_at=expires_at)
    violations = env.validate()
    if violations:
        return {"refusal": "PF-OPS-ENVELOPE-INVALID",
                "unlock": "envelope validation failed",
                "violations": violations}
    return env


def _dominant_executor(plan: ChangePlan) -> str:
    for s in plan.steps:
        spec = spec_for(s.action)
        if spec:
            return spec.executor
    return ""


def execute(op: Operation, env: ExecutionEnvelope, *,
            approvals: list[Approval],
            transports: dict[str, Any] | None = None,
            ledger: OperationLedger | None = None,
            locks: LockTable | None = None,
            dry_run: bool = True,
            break_glass: BreakGlass | None = None,
            preconditions: dict[str, Any] | None = None,
            at: str | None = None) -> dict[str, Any]:
    """§8 execution stages: approval → preconditions → locks → steps.
    `dry_run=True` is the default; callers must opt out explicitly."""
    ledger = ledger or OperationLedger()
    locks = locks or LockTable()
    transports = transports or {}

    # 1. hash-bound approval re-check (TOCTOU)
    chk = check_approval(approvals, subject_hash=env.hash(),
                         scope=env.scope, params={},
                         break_glass=break_glass,
                         current_plan_hash=env.hash(), at=at)
    if not chk.ok:
        ledger.append("approval.denied", op.operation_id,
                      data={"refusal": chk.refusal})
        return {"ok": False, "stage": "approval",
                "refusal": chk.refusal}

    # 2. preconditions
    pc = check_preconditions(
        observation=(preconditions or {}).get("observation"),
        max_observation_age_s=(preconditions or {}).get(
            "max_observation_age_s", 900),
        plan_hash=env.change_plan_hash,
        current_plan_hash=(preconditions or {}).get(
            "current_plan_hash", env.change_plan_hash),
        policy_decision=(preconditions or {}).get("policy_decision"),
        approval_valid=True,
        maintenance_window=(preconditions or {}).get("maintenance_window"),
        freeze_active=(preconditions or {}).get("freeze_active", False),
        break_glass=chk.used_break_glass, at=at)
    if not pc["ok"]:
        ledger.append("precondition.failed", op.operation_id,
                      data=pc["refusal"])
        return {"ok": False, "stage": "preconditions",
                "refusal": pc["refusal"], "checks": pc["checks"]}

    # 3. locks
    lk = locks.acquire(op.resources or env.scope, op.operation_id, ledger)
    if "refusal" in lk:
        return {"ok": False, "stage": "locking", "refusal": lk}

    # 4. FSM — walk the canonical chain to executing; resume-safe: a step
    # whose completion is already legal-from-state is skipped.
    for st in ("planned", "simulated", "policy-reviewed",
               "awaiting-approval", "approved", "executing"):
        if op.state == st:
            continue
        r = op.transition(st, ledger)
        if "refusal" in r:
            locks.release(op.operation_id, ledger)
            return {"ok": False, "stage": f"transition→{st}",
                    "refusal": r, "state": op.state}

    # 5. DAG execution — waves; mutating steps need transports
    plan_steps = {s["step_id"]: s for s in env.actions}
    results: list[dict[str, Any]] = []
    idem_seen: set[str] = set()
    failed: list[str] = []
    for wave in _waves(env):
        for sid in wave:
            a = plan_steps[sid]
            spec = spec_for(a["action"])
            ex = executor_for(a["action"])
            step = ExecutionStep(step_id=sid, action=a["action"],
                                 params=a.get("params", {}))
            key = step.effect_key(env.change_plan_hash)
            if key in idem_seen:
                ledger.append("step.skipped", op.operation_id,
                              data={"step_id": sid,
                                    "reason": "idempotent-duplicate"})
                continue
            idem_seen.add(key)
            ledger.append("step.started", op.operation_id,
                          data={"step_id": sid, "action": a["action"],
                                "dry_run": dry_run})
            if spec is None or ex is None:
                r = {"ok": False, "refusal": {
                    "refusal": "PF-OPS-UNKNOWN-ACTION",
                    "unlock": f"{a['action']} not in vocabulary"}}
            else:
                t = transports.get(spec.executor)
                rec = ex.run_step(sid, a["action"], a.get("params", {}),
                                  transport=t, dry_run=dry_run)
                r = rec.to_dict()
            results.append(r)
            if r.get("ok"):
                ledger.append("step.completed", op.operation_id,
                              data={"step_id": sid,
                                    "receipt": r.get("receipt_hash")})
            else:
                failed.append(sid)
                ledger.append("step.failed", op.operation_id,
                              data={"step_id": sid,
                                    "refusal": r.get("refusal"),
                                    "error": r.get("error", "")[:400]})
                # stop the DAG — a failed dep blocks downstream
                blocked = [s for w in _waves(env) for s in w
                           if s not in {x["step_id"] for x in results}]
                for b in blocked:
                    ledger.append("step.skipped", op.operation_id,
                                  data={"step_id": b,
                                        "reason": f"dep-failed:{sid}"})
                op.transition("failed", ledger)
                locks.release(op.operation_id, ledger)
                return {"ok": False, "stage": "execute",
                        "failed_step": sid, "results": results,
                        "state": op.state}

    op.transition("verifying", ledger)
    locks.release(op.operation_id, ledger)
    return {"ok": True, "stage": "execute", "dry_run": dry_run,
            "results": results, "state": op.state,
            "ledger_tip": ledger.tip}


def _waves(env: ExecutionEnvelope) -> list[list[str]]:
    """Waves from step deps stored as params.__depends_on__ or envelope
    order — simple: use declared order unless depends_on is present."""
    deps = {a["step_id"]: set((a.get("params") or {}).get(
        "__depends_on__", [])) for a in env.actions}
    done: set[str] = set()
    out: list[list[str]] = []
    total = len(env.actions)
    while len(done) < total:
        w = [s for s, d in deps.items() if d <= done and s not in done]
        if not w:
            w = [s for s in deps if s not in done]   # malformed → all
        out.append(w)
        done.update(w)
    return out


def finalize_verify(op: Operation, ledger: OperationLedger,
                    verification_result: dict[str, Any]) -> dict[str, Any]:
    conv = verification_result.get("convergence", "unknown")
    target = {"converged": "converged", "partially-converged":
              "partially-converged", "not-converged": "failed",
              "regressed": "rollback-planned",
              "unknown": "unresolved"}.get(conv, "unresolved")
    if op.state == "verifying":
        r = op.transition(target, ledger, data={"convergence": conv})
        if "refusal" in r:
            return r
    ledger.append("verified", op.operation_id, data=verification_result)
    return {"operation_id": op.operation_id, "state": op.state,
            "convergence": conv}
