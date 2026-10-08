"""Cycle 4 phase T — Forge Lab V4 operations scenarios.

An ops scenario drives the governed pipeline end to end with scripted
transports — no real mutation. `ops.yaml` in the fixture declares the
intent, plan steps, policies, approvals, observation, transport stubs
and the expected terminal state/refusal:

    detect → intent → plan → simulate → risk → policy → approve →
    envelope → execute(dry-or-scripted) → verify → converge/rollback
"""

from __future__ import annotations

from typing import Any

import yaml

from platformforge.ops.approval import Approval, BreakGlass
from platformforge.ops.engine import assess_risk, decide, execute, finalize_verify, mint_envelope
from platformforge.ops.engine import plan as mkplan
from platformforge.ops.models import ChangeIntent, ExpectedDelta, PlanStep, Reason
from platformforge.ops.operation import LockTable, Operation, OperationLedger
from platformforge.ops.policy import Policy
from platformforge.ops.rollback import derive_rollback
from platformforge.ops.simulate import simulate


def _stub_transport(rc: int = 0, stdout: str = "ok", stderr: str = ""):
    calls: list[list[str]] = []

    def t(argv, cwd=None, timeout_s=None):
        calls.append(list(argv))
        return rc, stdout, stderr
    t.calls = calls
    return t


def run_ops_scenario(fixture_dir) -> dict[str, Any]:
    from pathlib import Path
    fx = Path(fixture_dir)
    doc = yaml.safe_load((fx / "ops.yaml").read_text())
    checks: list[str] = []
    failures: list[str] = []

    i = doc["intent"]
    intent = ChangeIntent(
        intent_id=i.get("intent_id", "lab-intent"),
        owner=i.get("owner", "lab"), requested_by=i.get("requested_by", "lab"),
        reason=Reason(**i.get("reason", {"type": "manual"})),
        target_resources=list(i.get("target_resources", [])),
        desired_change=dict(i.get("desired_change", {})))

    steps = [PlanStep(step_id=s["step_id"], action=s["action"],
                      params=dict(s.get("params", {})))
             for s in doc.get("steps", [])]
    ed = doc.get("expected_delta") or {}
    plan = mkplan(intent,
                  steps=steps,
                  expected_delta=ExpectedDelta(
                      adds=ed.get("adds", {}),
                      removes=ed.get("removes", {}),
                      changes=ed.get("changes", {})))
    checks.append("plan.built")

    # simulate
    sim = simulate(plan, level=doc.get("simulation_level", "S1"))
    checks.append(f"simulate:{sim.outcome}")

    # risk
    risk = assess_risk(plan, {"environment": doc.get("environment", "lab")})
    checks.append(f"risk:{risk['risk_class']}")

    # policy
    policies = [Policy(**p) for p in doc.get("policies", [])]
    decisions = [decide(plan, policies,
                        {"environment": doc.get("environment", "lab"),
                         "risk_class": risk["risk_class"]})] \
        if policies else []
    checks.append("policy:" + ",".join(d.decision for d in decisions)
                  if decisions else "policy:none")

    # rollback
    rb = derive_rollback([{"action": s["action"],
                           "params": dict(s.get("params", {}))}
                          for s in doc.get("steps", [])],
                         {"environment": doc.get("environment", "lab"),
                          "automatic_allowed": doc.get(
                              "auto_rollback", False)})
    checks.append(f"rollback:{rb.strategy}")

    # envelope
    env = mint_envelope(plan, execution_id="lab-ex",
                        decisions=decisions or [_allow_all()],
                        approvals=[], risk=risk, rollback=rb)
    if isinstance(env, dict):
        result = {"ok": False, "stage": "mint",
                  "refusal": env}
        return _check_expect(doc, result, checks, failures)

    # approvals
    env_hash = env.freeze()
    approvals = []
    for a in doc.get("approvals", []):
        sh = {"envelope": env_hash, "plan": plan.hash()}.get(
            a.get("binds", "envelope"), a.get("binds", ""))
        approvals.append(Approval(
            approval_id=a.get("approval_id", "ap"),
            subject_hash=sh,
            scope=list(a.get("scope", env.scope)),
            actor=a.get("actor", "approver"),
            role=a.get("role", "owner"),
            expires_at=a.get("expires_at", ""),
            actor_kind=a.get("actor_kind", "human")))
    bg = None
    if doc.get("break_glass"):
        b = doc["break_glass"]
        bg = BreakGlass(break_glass_id=b.get("ticket_id", "BG-1"),
                        actor=b.get("actor", "oncall"),
                        invocation_reason=b.get("reason", ""),
                        scope=list(b.get("scope", env.scope)),
                        expires_at=b.get("expires_at", ""))

    # transports
    transports = {}
    for name, stub in (doc.get("transports") or {}).items():
        transports[name] = _stub_transport(
            rc=stub.get("rc", 0), stdout=stub.get("stdout", "ok"))

    # conflicting op
    locks = LockTable()
    ledger = OperationLedger()
    op = Operation(operation_id="lab-op", intent_id=intent.intent_id,
                   resources=list(env.scope))
    if doc.get("conflicting_operation"):
        other = Operation(operation_id="other",
                          resources=list(env.scope))
        locks.acquire(other.resources, "other")

    result = execute(op, env, approvals=approvals,
                     transports=transports, ledger=ledger,
                     locks=locks, dry_run=doc.get("dry_run", True),
                     break_glass=bg,
                     preconditions={
                         "observation": doc.get("observation"),
                         "pre_state": doc.get("pre_state"),
                         "current_plan_hash":
                             doc.get("current_plan_hash",
                                     env.change_plan_hash),
                         "policy_decision": (decisions[0].decision
                                             if decisions else "allow"),
                         "environment": doc.get("environment", "lab"),
                         "maintenance_window":
                             doc.get("maintenance_window"),
                         "freeze_active": doc.get("freeze_active",
                                                  False),
                         "automatic_rollback": doc.get(
                             "auto_rollback", False)})

    # verify stage if execution passed
    if result.get("ok") and doc.get("verify"):
        v = doc["verify"]
        from platformforge.ops.verify import verify as do_verify
        vr = do_verify(expected_delta=ed,
                       observations=v.get("observations", {}),
                       slo_contract=v.get("slo"),
                       metrics=v.get("metrics"),
                       mutating=any(s.get("mutating", True)
                                    for s in doc.get("steps", [])))
        result["verify"] = vr.to_dict()
        result["final"] = finalize_verify(
            op, ledger, {"convergence": vr.convergence})
        result["state"] = op.state
        # rollback execution from the material-built plan (§30 pipeline;
        # lab/non-prod §123)
        if op.state == "rollback-planned":
            rbp = result.get("rollback_plan") or env.rollback
            if (rbp or {}).get("status") == "executable" and \
                    (rbp or {}).get("automatic"):
                from platformforge.ops.engine import execute_rollback
                result["rollback"] = execute_rollback(
                    op, env, transports=transports, ledger=ledger,
                    locks=locks,
                    completed_results=result.get("results"),
                    materials=result.get("materials"),
                    rollback_plan=rbp,
                    trigger={"type": "verification-failed",
                             "observed_delta": ed},
                    post_rollback_state=doc.get("post_rollback") or {},
                    dry_run=doc.get("dry_run", True))
                result["state"] = op.state

    result["checks"] = checks
    result["ledger_valid"] = ledger.verify_chain()
    result["ledger_events"] = [e.event for e in ledger.entries]
    return _check_expect(doc, result, checks, failures)


def _allow_all():
    from platformforge.ops.policy import PolicyDecision
    return PolicyDecision(policy_id="lab-default", decision="allow",
                          reason="lab default allow")


def _check_expect(doc, result, checks, failures):
    exp = doc.get("expect", {})
    if "ok" in exp and result.get("ok") != exp["ok"]:
        failures.append(f"expected ok={exp['ok']} got {result.get('ok')}")
    if exp.get("stage") and result.get("stage") != exp["stage"]:
        failures.append(f"stage: expected {exp['stage']} "
                        f"got {result.get('stage')}")
    if exp.get("state"):
        got = result.get("state") or (result.get("final") or {}).get("state")
        if got != exp["state"]:
            failures.append(f"state: expected {exp['state']} got {got}")
    if exp.get("refusal"):
        ref = (result.get("refusal") or {})
        want = exp["refusal"]
        if ref.get("refusal") != want and want not in str(ref):
            failures.append(f"refusal: expected {want} got {ref}")
    if exp.get("convergence"):
        got = (result.get("verify") or {}).get("convergence")
        if got != exp["convergence"]:
            failures.append(f"convergence: expected "
                            f"{exp['convergence']} got {got}")
    if exp.get("ledger_event") and exp["ledger_event"] not in (
            result.get("ledger_events") or []):
        failures.append(f"missing ledger event "
                        f"{exp['ledger_event']}")
    if not result.get("ledger_valid", True):
        failures.append("ledger chain invalid")
    return {"scenario": doc.get("name", "ops-scenario"),
            "passed": not failures, "failures": failures,
            "checks": checks,
            "result": {k: v for k, v in result.items()
                       if k in ("ok", "stage", "state", "refusal",
                                "convergence", "dry_run")}}
