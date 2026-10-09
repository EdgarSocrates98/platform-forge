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
from platformforge.ops.rollback import RollbackPlan, build_rollback_plan, compensate_for, derive_rollback
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


def assess_risk(plan: ChangePlan, context: dict[str, Any] | None = None,
                rollback_status: str | None = None
                ) -> dict[str, Any]:
    """Per-step risk assessments + plan ceiling (max class wins).
    Cycle 4.1: the material-built rollback status feeds both
    rollback_confidence and the reversibility class (worst-of)."""
    from platformforge.ops.risk import RISK_RANK, reversibility_for_status, rollback_confidence
    ctx = context or {}
    per_step = []
    worst = "R0"
    rb_conf = rollback_confidence(rollback_status)
    for s in plan.steps:
        rev = classify_reversibility(s.action, s.params, ctx)
        rev = reversibility_for_status(rollback_status, rev)
        spec = spec_for(s.action)
        step_status = rollback_status
        if spec and spec.rollback_strategy in ("manual-only",
                                               "impossible", "unknown"):
            step_status = spec.rollback_strategy if \
                spec.rollback_strategy != "unknown" else "unresolved"
        a = assess(s.action, s.params,
                   {**ctx, "reversibility": rev,
                    "rollback_confidence":
                        rollback_confidence(step_status)})
        per_step.append({"step_id": s.step_id, "action": s.action,
                         "rollback_status": step_status or "unknown",
                         **a.to_dict()})
        if RISK_RANK[a.risk_class] > RISK_RANK[worst]:
            worst = a.risk_class
    out = {"plan_id": plan.plan_id, "risk_class": worst,
           "steps": per_step,
           "rollback_confidence": rb_conf}
    if rollback_status:
        out["rollback_status"] = rollback_status
    return out


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
    # Cycle 4.1 §E — a mutating plan with NO declared delta refuses to
    # mint. `unknown_dimensions` counts as an honest declaration; a
    # completely empty delta does not.
    if delta_refusal(plan) is not None:
        return delta_refusal(plan)
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


def delta_refusal(plan: ChangePlan) -> dict[str, Any] | None:
    """Cycle 4.1 — mutating steps require an ExpectedDelta declaration
    (adds/removes/changes OR explicit unknown_dimensions). Read-only
    plans (validate/show/observe/diff) may omit it."""
    ed = plan.expected_delta
    declared = bool(getattr(ed, "adds", None)
                    or getattr(ed, "removes", None)
                    or getattr(ed, "changes", None)
                    or getattr(ed, "unknown_dimensions", None))
    if declared:
        return None
    mutating = [s.action for s in plan.steps
                if (spec_for(s.action) or _MISSING).mutating]
    if mutating:
        return {"refusal": "PF-OPS-NO-DELTA",
                "unlock": "declare expected_delta (adds/removes/changes "
                          "or explicit unknown_dimensions) — mutating "
                          "plans cannot mint without an expected "
                          "outcome",
                "mutating_steps": mutating}
    return None


class _MissingSpec:
    mutating = True   # unknown action → treat as mutating (conservative)


_MISSING = _MissingSpec()


def _dominant_executor(plan: ChangePlan) -> str:
    for s in plan.steps:
        spec = spec_for(s.action)
        if spec:
            return spec.executor
    return ""


_REQUIRE_DECISIONS = {
    "require-dual-human": "dual-human",
    "require-security-review": "security-review",
    "require-owner": "resource-owner",
    "require-platform-owner": "platform-owner",
}


def required_approval_type(env: ExecutionEnvelope,
                           environment: str = "") -> str:
    """§43/§54 — `require-*` policy decisions and prod R4+ risk escalate
    the approval type an envelope demands (break-glass still bypasses
    with its own audit trail)."""
    for d in env.policy_decisions or []:
        eff = d.get("decision", "")
        if eff in _REQUIRE_DECISIONS:
            return _REQUIRE_DECISIONS[eff]
    risk_class = (env.risk or {}).get("risk_class", "")
    if environment == "prod" and risk_class in ("R4", "R5"):
        return "dual-human"
    if risk_class == "R5":
        return "dual-human"
    return ""


def execute(op: Operation, env: ExecutionEnvelope, *,
            approvals: list[Approval],
            transports: dict[str, Any] | None = None,
            ledger: OperationLedger | None = None,
            locks: LockTable | None = None,
            dry_run: bool = True,
            break_glass: BreakGlass | None = None,
            preconditions: dict[str, Any] | None = None,
            material_store=None,
            at: str | None = None) -> dict[str, Any]:
    """§8 execution stages: approval → preconditions → locks → steps.
    `dry_run=True` is the default; callers must opt out explicitly."""
    ledger = ledger or OperationLedger()
    locks = locks or LockTable()
    transports = transports or {}

    # 1. hash-bound approval re-check (TOCTOU)
    # §61 — parameter bounds check against the *actual* step params:
    # approving replicas 3→5 must not authorize 3→50.
    merged_params: dict[str, Any] = {}
    for a in env.actions:
        merged_params.update(a.get("params") or {})
    chk = check_approval(approvals, subject_hash=env.hash(),
                         scope=env.scope, params=merged_params,
                         required_type=required_approval_type(
                             env, (preconditions or {}).get(
                                 "environment", "")),
                         break_glass=break_glass,
                         current_plan_hash=env.hash(), at=at)
    if not chk.ok:
        ledger.append("approval.denied", op.operation_id,
                      data={"refusal": chk.refusal})
        return {"ok": False, "stage": "approval",
                "refusal": chk.refusal}

    # 2. preconditions — including TOCTOU resource-state comparison
    # (§57–58) and owner drift when the caller supplies them.
    pc = check_preconditions(
        observation=(preconditions or {}).get("observation"),
        max_observation_age_s=(preconditions or {}).get(
            "max_observation_age_s", 900),
        expected_resource_state=(preconditions or {}).get(
            "expected_resource_state"),
        current_resource_state=(preconditions or {}).get(
            "current_resource_state"),
        plan_hash=env.change_plan_hash,
        current_plan_hash=(preconditions or {}).get(
            "current_plan_hash", env.change_plan_hash),
        owner=(preconditions or {}).get("owner", ""),
        current_owner=(preconditions or {}).get("current_owner", ""),
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

    # 5. DAG execution — waves; mutating steps need transports.
    # Cycle 4.1 §30: every mutating step captures RollbackMaterial
    # (pre-state BEFORE the step, execution result AFTER) into the
    # content-addressed store — never reused forward params.
    from platformforge.ops.material import MaterialStore, capture_material
    mstore = material_store or MaterialStore()
    pre_state_ctx = (preconditions or {}).get("pre_state") or {}
    sot_ctx = (preconditions or {}).get("sot") or {}
    materials: dict[str, Any] = {}
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
            mat = None
            if spec and spec.mutating:
                mat = capture_material(
                    a["action"], sid, op.operation_id,
                    a.get("params", {}),
                    spec.pre_state_requirements,
                    pre_state=_capture_pre_state(
                        a["action"], a.get("params", {}),
                        pre_state_ctx.get(sid)),
                    source_of_truth=sot_ctx.get(sid) or
                    sot_ctx.get("__default__"),
                    provenance="observed" if pre_state_ctx.get(sid)
                    else "declared")
            ledger.append("step.started", op.operation_id,
                          data={"step_id": sid, "action": a["action"],
                                "dry_run": dry_run,
                                "material": mat.hash() if mat else None})
            if spec is None or ex is None:
                r = {"ok": False, "refusal": {
                    "refusal": "PF-OPS-UNKNOWN-ACTION",
                    "unlock": f"{a['action']} not in vocabulary"}}
            else:
                t = transports.get(spec.executor)
                rec = ex.run_step(sid, a["action"], a.get("params", {}),
                                  transport=t, dry_run=dry_run)
                r = rec.to_dict()
            if mat is not None:
                # post-result capture (§12/§31) + persist immutable
                mat.execution_result.update(
                    {k: v for k, v in (r.get("outputs") or {}).items()
                     if k in spec.post_result_requirements
                     or k.endswith("commit") or k in ("pr", "output")})
                for k in spec.post_result_requirements:
                    if k in r and k not in mat.execution_result:
                        mat.execution_result[k] = r[k]
                mstore.put(mat)
                r["material_hash"] = mat.hash()
                materials[sid] = mat
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
    # §30 — rebuild the rollback plan against captured materials so the
    # post-execution plan is honest about executability.
    fwd_steps = [{"step_id": a["step_id"], "action": a["action"],
                  "params": a.get("params", {})} for a in env.actions]
    rb = build_rollback_plan(
        fwd_steps, materials=materials,
        context={"environment": (preconditions or {}).get(
            "environment", "unknown"),
            "automatic_allowed": (preconditions or {}).get(
                "automatic_rollback", False)})
    return {"ok": True, "stage": "execute", "dry_run": dry_run,
            "results": results, "state": op.state,
            "ledger_tip": ledger.tip,
            "materials": {sid: m.to_dict() for sid, m
                          in materials.items()},
            "material_hashes": {sid: m.hash() for sid, m
                                in materials.items()},
            "rollback_plan": rb.to_dict()}


def _capture_pre_state(action: str, params: dict[str, Any],
                       ctx_state: dict[str, Any] | None
                       ) -> dict[str, Any]:
    """§8/§31 — assemble the pre-change snapshot for one step.

    Sources, weakest→strongest:
      1. params the action itself declares (`current_replicas`,
         `resource_version`, `to_revision`…)
      2. caller-supplied `pre_state` ctx (observation-sourced values
         per step_id) — wins on conflict, provenance observed.
    """
    pre: dict[str, Any] = {}
    if action == "kubernetes.scale":
        if params.get("current_replicas") is not None:
            pre["replicas"] = params["current_replicas"]
        if params.get("resource_version"):
            pre["resource_version"] = params["resource_version"]
    elif action == "kubernetes.annotate":
        if params.get("previous_annotations") is not None:
            pre["annotations"] = dict(params["previous_annotations"])
        if params.get("resource_version"):
            pre["resource_version"] = params["resource_version"]
    elif action == "kubernetes.rollout_restart":
        if params.get("current_revision") is not None:
            pre["revision"] = params["current_revision"]
    elif action == "argocd.sync":
        for k in ("history_id", "previous_revision", "repo",
                  "git_revert_commit"):
            if params.get(k) is not None:
                pre[k] = params[k]
    elif action in ("terraform.apply_saved_plan",
                    "tofu.apply_saved_plan"):
        for k in ("source_ref", "workspace", "state_serial",
                  "resource_addresses", "plan_hash"):
            if params.get(k) is not None:
                pre[k] = params[k]
    elif action in ("git.apply_patch", "git.commit", "git.open_pr"):
        for k in ("pre_change_commit", "repo"):
            if params.get(k) is not None:
                pre[k] = params[k]
    elif action == "git.delete_branch":
        if params.get("branch_sha") is not None:
            pre["branch_sha"] = params["branch_sha"]
    if ctx_state:
        for k, v in ctx_state.items():   # observed wins (§7)
            if v is not None:
                pre[k] = v
    return pre


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


def execute_rollback(op: Operation, env: ExecutionEnvelope, *,
                     transports: dict[str, Any] | None = None,
                     ledger: OperationLedger | None = None,
                     locks: LockTable | None = None,
                     completed_results: list[dict[str, Any]] | None = None,
                     materials: dict[str, Any] | None = None,
                     rollback_plan: dict[str, Any] | None = None,
                     trigger: dict[str, Any] | None = None,
                     post_rollback_state: dict[str, Any] | None = None,
                     dry_run: bool = True,
                     at: str | None = None) -> dict[str, Any]:
    """§40–43/§119–127/§149–160 — execute a rollback built from
    MATERIAL, under the same locks and idempotency as the forward pass.

    - `trigger` (§98): typed cause {type, verification_id,
      observed_delta, slo_evidence, at}. Never a bare string.
    - `rollback_plan` (v2): built from captured materials. Only
      status=executable runs typed actions; manual-only/impossible/
      unresolved/requires-replan refuse honestly.
    - Idempotent (§156): an already rolled-back op returns the prior
      receipt instead of re-executing; same locks as forward (§158).
    - A failed rollback step lands in `failed` with stage=rollback —
      never `rolled-back` (§149–153); no automatic second rollback.
    - `post_rollback_state` (§41–43): caller-supplied observation used
      to verify restored|partially-restored|regressed|unknown.
    """
    ledger = ledger or OperationLedger()
    locks = locks or LockTable()
    trigger = dict(trigger or {"type": "manual"})
    rb = dict(rollback_plan or env.rollback or {})
    strategy = rb.get("strategy", "unknown")
    status = rb.get("status", "unresolved")

    # §156 — duplicate rollback request → idempotent receipt
    if op.state == "rolled-back":
        return {"ok": True, "state": op.state,
                "idempotent": "already-rolled-back"}

    # §36 — only executable plans execute; everything else is an
    # honest refusal, never an invented action
    if status != "executable":
        return {"ok": False, "state": op.state,
                "refusal": {"refusal": "PF-OPS-ROLLBACK-NOT-EXECUTABLE",
                            "unlock": f"rollback status is "
                                      f"'{status}' — manual remediation "
                                      "or a new governed plan required"},
                "strategy": strategy, "status": status,
                "replans": rb.get("replans", []),
                "limitations": rb.get("limitations", [])}

    rb_actions = list(rb.get("actions", []))
    mats = dict(materials or {})
    if not rb_actions and completed_results:
        comp = compensate_for([{"step_id": r.get("step_id"),
                                "action": r.get("action"),
                                "params": r.get("outputs", {}).get(
                                    "params", {}),
                                "status": "completed" if r.get("ok")
                                else "failed"}
                               for r in completed_results],
                              materials=mats)
        rb_actions = comp["compensating_actions"]
        if comp["manual_steps"]:
            rb.setdefault("limitations", []).append(
                f"manual compensation needed for {comp['manual_steps']}")
    if not rb_actions:
        return {"ok": False, "state": op.state,
                "refusal": {"refusal": "PF-OPS-ROLLBACK-EMPTY",
                            "unlock": "no rollback actions derivable — "
                                      "manual remediation required"}}

    # §158 — rollback holds the same resource locks as the forward op
    lk = locks.acquire(op.resources or env.scope, op.operation_id,
                       ledger)
    if "refusal" in lk:
        return {"ok": False, "state": op.state, "stage": "locking",
                "refusal": lk}

    # §159 — rollback preconditions: the resource must still match the
    # failed-forward state; external drift → human review, never blind
    # revert of someone else's change.
    precondition_refusals = _rollback_preconditions(
        mats, rb.get("steps", []))
    if precondition_refusals:
        locks.release(op.operation_id, ledger)
        return {"ok": False, "state": op.state,
                "stage": "rollback-preconditions",
                "refusal": {"refusal": "PF-OPS-ROLLBACK-PRECONDITION",
                            "unlock": "resource no longer matches "
                                      "failed-forward state — human "
                                      "review required (§159)",
                            "details": precondition_refusals}}

    # legal walk into rolling-back
    for st in ("rollback-planned", "rolling-back"):
        if op.state == st:
            continue
        if st == "rollback-planned" and op.state in \
                ("executing", "rolling-back"):
            continue  # executing may jump straight to rolling-back
        r = op.transition(st, ledger, data={"strategy": strategy})
        if "refusal" in r:
            locks.release(op.operation_id, ledger)
            return {"ok": False, "state": op.state, "refusal": r}

    ledger.append("rollback.started", op.operation_id,
                  data={"strategy": strategy, "status": status,
                        "trigger": trigger,
                        "material_hashes": rb.get("material_hashes", []),
                        "actions": len(rb_actions)})
    results: list[dict[str, Any]] = []
    transports = transports or {}
    for i, a in enumerate(rb_actions):
        sid = f"rb-{i}-{a.get('action', '?')}"
        spec = spec_for(a.get("action", ""))
        ex = executor_for(a.get("action", ""))
        ledger.append("step.started", op.operation_id,
                      data={"step_id": sid, "action": a.get("action"),
                            "rollback": True, "dry_run": dry_run})
        if spec is None or ex is None:
            r = {"ok": False, "refusal": {
                "refusal": "PF-OPS-UNKNOWN-ACTION",
                "unlock": f"{a.get('action')} not in vocabulary"}}
        else:
            rec = ex.run_step(sid, a["action"], a.get("params", {}),
                              transport=transports.get(spec.executor),
                              dry_run=dry_run)
            r = rec.to_dict()
        results.append(r)
        if r.get("ok"):
            ledger.append("step.completed", op.operation_id,
                          data={"step_id": sid,
                                "receipt": r.get("receipt_hash"),
                                "rollback": True})
        else:
            ledger.append("step.failed", op.operation_id,
                          data={"step_id": sid,
                                "refusal": r.get("refusal"),
                                "rollback": True})
            # §149–153 — failed rollback → failed + stage detail +
            # human escalation; NO automatic rollback-of-rollback
            op.transition("failed", ledger,
                          data={"stage": "rollback",
                                "escalation": "human-required"})
            locks.release(op.operation_id, ledger)
            return {"ok": False, "state": op.state,
                    "stage": "rollback",
                    "rollback_failed": True,
                    "escalation": "human-required",
                    "failed_step": sid, "results": results}

    # §41–43 — rollback verification: command success ≠ restored.
    ver = verify_rollback(mats, post_rollback_state or {})
    ledger.append("rollback.completed", op.operation_id,
                  data={"strategy": strategy,
                        "actions": len(results),
                        "rollback_verification": ver["convergence"]})
    op.transition("rolled-back", ledger,
                  data={"rollback_verification": ver["convergence"]})
    locks.release(op.operation_id, ledger)
    # §40 — rollback receipt: trigger + material + strategy + result +
    # verification, hash-linked to the forward operation
    receipt = {
        "operation_id": op.operation_id,
        "stage": "rollback",
        "result": ver["convergence"],
        "trigger": trigger,
        "strategy": strategy,
        "material_hashes": rb.get("material_hashes", []),
        "rollback_plan_ref": env.hash(),
        "actions": len(results),
        "rollback_verification": ver,
        "comparisons": ver.get("comparisons", []),
    }
    return {"ok": ver["convergence"] in ("restored", "not-applicable"),
            "state": op.state, "results": results,
            "strategy": strategy,
            "rollback_verification": ver["convergence"],
            "receipt": receipt}


def _rollback_preconditions(materials: dict[str, Any],
                            plan_steps: list[dict[str, Any]]
                            ) -> list[dict[str, Any]]:
    """§159 — per-step precondition records. A material whose
    `pre_state` carries `current_matches_forward=False` (caller flags
    external drift between forward failure and rollback attempt)
    requires human review."""
    bad = []
    step_map = {s.get("step_id"): s for s in plan_steps}
    for sid, mat in materials.items():
        m = mat.to_dict() if hasattr(mat, "to_dict") else dict(mat)
        pre = m.get("pre_state", {})
        if pre.get("current_matches_forward") is False:
            bad.append({"step_id": sid,
                        "reason": "external-change-detected",
                        "action": step_map.get(sid, {}).get("action")})
    return bad


def verify_rollback(materials: dict[str, Any],
                    post_state: dict[str, Any] | None = None
                    ) -> dict[str, Any]:
    """§41–43 — compare captured pre-state with the post-rollback
    observation. Restored only when every captured dimension matches.

    `post_state`: {step_id: {dim: observed_value}} from a fresh
    observation after rollback. Missing observations → unknown, never
    restored-by-assumption.
    """
    post = post_state or {}
    if not materials:
        return {"convergence": "not-applicable",
            "comparisons": [],
            "note": "no materials captured — nothing to verify"}
    if not post:
        return {"convergence": "unknown",
                "comparisons": [],
                "note": "no post-rollback observation — cannot claim "
                        "restored (§43)"}
    comps: list[dict[str, Any]] = []
    restored = regressed = missing = 0
    # concurrency/provenance tokens are captured for preconditions,
    # not restorable values — a new write always bumps them
    non_restorable = {"resource_version", "uid",
                      "current_matches_forward", "generation"}
    for sid, mat in materials.items():
        m = mat.to_dict() if hasattr(mat, "to_dict") else dict(mat)
        want = {k: v for k, v in m.get("pre_state", {}).items()
                if k not in non_restorable}
        got = post.get(sid) or {}
        for dim, expected in want.items():
            observed = got.get(dim, "<unobserved>")
            if observed == "<unobserved>":
                outcome = "unobserved"
                missing += 1
            elif observed == expected:
                outcome = "restored"
                restored += 1
            else:
                outcome = "different"
                regressed += 1
            comps.append({"step_id": sid, "dimension": dim,
                          "expected": expected, "observed": observed,
                          "outcome": outcome})
    total = restored + regressed + missing
    if missing == total:
        conv = "unknown"
    elif regressed:
        conv = "regressed" if restored == 0 else "partially-restored"
    elif missing:
        conv = "partially-restored"
    else:
        conv = "restored"
    return {"convergence": conv, "comparisons": comps,
            "restored": restored, "different": regressed,
            "unobserved": missing}
