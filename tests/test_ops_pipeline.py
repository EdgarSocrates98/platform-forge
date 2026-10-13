"""End-to-end pipeline: intent → plan → policy → approve → envelope →
execute (dry-run) → verify → converge. Plus the refusal paths."""

from platformforge.ops.approval import Approval
from platformforge.ops.engine import assess_risk, decide, execute, finalize_verify, mint_envelope, propose
from platformforge.ops.engine import plan as mkplan
from platformforge.ops.models import ChangeIntent, ExpectedDelta, PlanStep, Reason
from platformforge.ops.operation import LockTable, Operation, OperationLedger
from platformforge.ops.policy import Policy
from platformforge.ops.rollback import derive_rollback
from platformforge.ops.simulate import simulate


def _intent():
    return ChangeIntent(
        intent_id="scale-web", owner="team-a", requested_by="bob",
        reason=Reason(type="drift", drift_ids=["d1"]),
        target_resources=["k8s:prod/apps/Deployment/web"],
        desired_change={"replicas": 3})


def _plan(intent):
    return mkplan(intent, steps=[
        PlanStep(step_id="scale", action="kubernetes.scale",
                 params={"kind": "Deployment", "name": "web",
                         "namespace": "prod", "replicas": 3,
                         "current_replicas": 5})],
        expected_delta=ExpectedDelta(
            changes={"resources": [{"id": "dep/web",
                                    "replicas": [5, 3]}]}))


def _policies():
    return [Policy(policy_id="allow-r2-dev", priority=10,
                   when={"environment": "dev"},
                   then={"decision": "allow", "reason": "dev+low-risk"})]


def _fake_transport(calls):
    def t(argv, cwd=None, timeout_s=None):
        calls.append(argv)
        return 0, "scaled", ""
    return t


def _approve_env(env, scope=("k8s:prod/apps/Deployment/web",)):
    return [Approval(approval_id="ap1", subject_hash=env.hash(),
                     scope=list(scope), actor="alice", role="owner",
                     type="single-human")]


def test_full_pipeline_dry_run_to_converged():
    intent = _intent()
    p = propose(intent, resources=[{
        "resource_id": "k8s:prod/apps/Deployment/web",
        "annotations": {"argocd.argoproj.io/instance": "app_prod-web"}}],
        sot_context={"gitops_apps": {"app_prod-web":
                                     {"repository": "git@org/infra"}}})
    assert p["ok"] and p["resolutions"][0]["resolved"]

    plan = _plan(intent)
    sim = simulate(plan, level="S1")
    assert sim.outcome in ("pass", "partial")

    risk = assess_risk(plan, {"environment": "prod"})
    assert risk["steps"][0]["risk_class"] in ("R2", "R3")

    env = mint_envelope(plan, execution_id="ex-1",
                        decisions=[decide(plan, _policies(),
                                          {"environment": "dev"})],
                        approvals=[_approve_env.__wrapped__ if False else
                                   Approval(approval_id="pre",
                                            subject_hash="pending",
                                            scope=list(plan.affected_resources),
                                            actor="alice")],
                        risk=risk,
                        rollback=derive_rollback(
                            [{"action": "kubernetes.scale",
                              "params": {"replicas": 3}}],
                            {"environment": "prod"}))
    assert not isinstance(env, dict)          # minted, not refused
    env_hash = env.freeze()

    aps = [Approval(approval_id="ap1", subject_hash=env_hash,
                    scope=list(env.scope), actor="alice", role="owner")]
    calls = []
    op = Operation(operation_id="op-1", resources=list(env.scope))
    r = execute(op, env, approvals=aps,
                transports={"kubernetes": _fake_transport(calls)},
                ledger=OperationLedger(), locks=LockTable(),
                dry_run=True,
                preconditions={"observation": None,
                               "current_plan_hash": env.change_plan_hash})
    # precondition fails — no observation supplied (fail closed)
    assert not r["ok"] and r["stage"] == "preconditions"

    # fresh complete observation → executes (dry-run)
    obs = {"captured_at": "2999-01-01T00:00:00Z",
           "coverage": {"complete": True}}
    op2 = Operation(operation_id="op-2", resources=list(env.scope))
    led = OperationLedger()
    r2 = execute(op2, env, approvals=aps,
                 transports={"kubernetes": _fake_transport(calls)},
                 ledger=led, locks=LockTable(), dry_run=True,
                 preconditions={"observation": obs,
                                "current_plan_hash": env.change_plan_hash})
    assert r2["ok"] and op2.state == "verifying"
    assert "--dry-run=server" in calls[-1]

    vres = {"convergence": "converged"}
    fin = finalize_verify(op2, led, vres)
    assert fin["state"] == "converged"
    assert led.verify_chain()


def test_no_approval_never_executes():
    intent = _intent()
    plan = _plan(intent)
    env = mint_envelope(plan, execution_id="ex-2",
                        decisions=[decide(plan, _policies(),
                                          {"environment": "dev"})],
                        approvals=[],
                        risk=assess_risk(plan, {"environment": "dev"}),
                        rollback=None)
    # approvals=[] in envelope → mint still ok if policy decision allowed;
    # execution requires a bound approval
    op = Operation(operation_id="op-3", resources=list(env.scope))
    r = execute(op, env, approvals=[], transports={},
                ledger=OperationLedger(), dry_run=False)
    assert not r["ok"] and r["stage"] == "approval"
    assert r["refusal"]["refusal"] == "PF-OPS-NO-APPROVAL"


def test_policy_deny_never_mints():
    plan = _plan(_intent())
    deny = Policy(policy_id="no-prod", priority=1,
                  when={"environment": "prod"},
                  then={"decision": "deny", "reason": "prod frozen"})
    r = mint_envelope(plan, execution_id="ex-3",
                      decisions=[decide(plan, [deny],
                                        {"environment": "prod"})],
                      approvals=[], risk={}, rollback=None)
    assert r["refusal"] == "PF-OPS-POLICY-BLOCK"


def test_simulation_declares_limits():
    plan = _plan(_intent())
    r = simulate(plan, level="S4")
    assert r.limitations == sim_limits() or "dry-run" in r.limitations[0]
    assert "unknowns" in r.to_dict()


def sim_limits():
    from platformforge.ops.simulate import LEVEL_LIMITS
    return LEVEL_LIMITS["S4"]
