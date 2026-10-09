"""Phase U — adversarial property tests (cycle4 §U invariants).

Each test asserts a *safety invariant* survives attack-like inputs:
approval bypass, plan mutation, stale evidence, shell injection,
actor forgery, lock conflicts, resume duplication, and the
command-success-≠-converged boundary.
"""

import json

from platformforge.ops.actions import FORBIDDEN_ACTIONS, validate_action
from platformforge.ops.approval import Approval, BreakGlass, check_approval
from platformforge.ops.engine import execute
from platformforge.ops.envelope import ExecutionEnvelope
from platformforge.ops.operation import LockTable, Operation, OperationLedger
from platformforge.ops.risk import assess


def _env(scope=None, action="kubernetes.scale", **kw):
    e = ExecutionEnvelope(
        execution_id="ex", intent_id="i", change_plan_hash="sha256:p",
        executor="kubernetes",
        actions=[{"step_id": "s1", "action": action,
                  "params": {"kind": "Deployment", "name": "w",
                             "namespace": "apps", "replicas": 3}}],
        scope=list(scope or ["k8s:lab/apps/Deployment/web"]),
        policy_decisions=[{"decision": "allow", "effective": "allow",
                           "policy_id": "p1"}])
    return e


def _ok_transport(argv, cwd=None, timeout_s=None):
    return 0, "ok", ""


OBS = {"captured_at": "2999-01-01T00:00:00Z",
       "coverage": {"complete": True}}


def _exec(env, aps, **kw):
    pc = kw.pop("preconditions",
                {"observation": OBS,
                 "current_plan_hash": env.change_plan_hash})
    return execute(
        Operation(operation_id="op", resources=list(env.scope)),
        env, approvals=aps,
        transports={"kubernetes": _ok_transport},
        ledger=OperationLedger(), locks=LockTable(),
        preconditions=pc,
        **kw)


# --- approval attacks ----------------------------------------------------

def test_no_approval_no_execute():
    r = _exec(_env(), [])
    assert r["refusal"]["refusal"] == "PF-OPS-NO-APPROVAL"


def test_hash_mismatch_rejected():
    env = _env()
    h = env.freeze()
    env.actions[0]["params"]["replicas"] = 99   # mutate after approval
    ap = Approval(subject_hash=h, scope=list(env.scope), actor="alice")
    r = _exec(env, [ap])
    assert not r["ok"] and r["stage"] == "approval"


def test_expired_approval_rejected():
    env = _env()
    ap = Approval(subject_hash=env.freeze(), scope=list(env.scope),
                  actor="alice", expires_at="2000-01-01T00:00:00Z")
    r = _exec(env, [ap])
    assert r["refusal"]["refusal"] == "PF-OPS-APPROVAL-EXPIRED"


def test_scope_mismatch_rejected():
    env = _env()
    ap = Approval(subject_hash=env.freeze(), scope=["other/scope"],
                  actor="alice")
    r = _exec(env, [ap])
    assert r["refusal"]["refusal"] in ("PF-OPS-APPROVAL-SCOPE",
                                      "PF-OPS-NO-APPROVAL")


def test_agent_cannot_fabricate_human_approval():
    env = _env()
    ap = Approval(subject_hash=env.freeze(), scope=list(env.scope),
                  actor="bot", actor_kind="agent")
    r = _exec(env, [ap])
    assert not r["ok"]
    # but explicit host opt-in would pass
    chk = check_approval([ap], subject_hash=env.hash(),
                         scope=list(env.scope),
                         current_plan_hash=env.hash(),
                         allow_actor_kinds=("human", "agent"))
    assert chk.ok


def test_signed_approval_tamper_detected():
    env = _env()
    ap = Approval(subject_hash=env.freeze(), scope=list(env.scope),
                  actor="alice")
    ap.sign()
    ap.scope = ["tampered/scope"]              # attacker widens scope
    r = _exec(env, [ap])
    assert r["refusal"]["refusal"] == "PF-OPS-APPROVAL-TAMPERED"


def test_valid_signature_accepted():
    env = _env()
    ap = Approval(subject_hash=env.freeze(), scope=list(env.scope),
                  actor="alice")
    ap.sign()
    r = _exec(env, [ap])
    assert r["ok"]


def test_break_glass_needs_reason_actor_ttl_scope():
    env = _env()
    bg = BreakGlass(actor="oncall")            # no reason/ttl/scope
    r = _exec(env, [], break_glass=bg)
    assert not r["ok"]
    assert "BG-" in r["refusal"]["refusal"]


# --- injection / bypass ---------------------------------------------------

def test_shell_action_never_valid():
    for a in FORBIDDEN_ACTIONS:
        assert validate_action(a, {})["refusal"] == "PF-OPS-UNSTRUCTURED"


def test_envelope_rejects_forged_action():
    env = _env(action="shell.run")
    env.actions[0]["action"] = "shell.run"
    codes = {v["refusal"] for v in env.validate()}
    assert codes & {"PF-OPS-UNSTRUCTURED", "PF-OPS-UNKNOWN-ACTION"}


def test_param_injection_is_data_not_command():
    env = _env()
    env.actions[0]["params"]["name"] = "w; rm -rf /"
    h = env.freeze()
    ap = Approval(subject_hash=h, scope=list(env.scope), actor="alice")
    calls = []
    def t(argv, cwd=None, timeout_s=None):
        calls.append(argv)
        return 0, "ok", ""
    r = execute(Operation(operation_id="op", resources=list(env.scope)),
                env, approvals=[ap],
                transports={"kubernetes": t},
                ledger=OperationLedger(), locks=LockTable(), dry_run=True,
                preconditions={"observation": OBS,
                               "current_plan_hash": env.change_plan_hash})
    assert r["ok"]
    # the payload stays an argv element — never concatenated into a shell
    assert any("w; rm -rf /" in a for a in calls[-1])


# --- state / ledger invariants -------------------------------------------

def test_stale_observation_blocks():
    env = _env()
    ap = Approval(subject_hash=env.freeze(), scope=list(env.scope),
                  actor="alice")
    r = _exec(env, [ap], preconditions={
        "observation": {"captured_at": "2000-01-01T00:00:00Z",
                        "coverage": {"complete": True}},
        "current_plan_hash": env.change_plan_hash})
    assert r["refusal"]["refusal"] == "PF-OPS-PRECONDITION-FAILED"


def test_locks_prevent_conflicts():
    env = _env()
    locks = LockTable()
    other = Operation(operation_id="other", resources=list(env.scope))
    locks.acquire(other.resources, "other")
    ap = Approval(subject_hash=env.freeze(), scope=list(env.scope),
                  actor="alice")
    r = execute(Operation(operation_id="op", resources=list(env.scope)),
                env, approvals=[ap],
                transports={"kubernetes": _ok_transport},
                ledger=OperationLedger(), locks=locks,
                preconditions={"observation": OBS,
                               "current_plan_hash": env.change_plan_hash})
    assert not r["ok"] and r["stage"] == "locking"


def test_resume_after_converge_refused():
    env = _env()
    ap = Approval(subject_hash=env.freeze(), scope=list(env.scope),
                  actor="alice")
    op = Operation(operation_id="op", resources=list(env.scope))
    led = OperationLedger()
    r1 = execute(op, env, approvals=[ap],
                 transports={"kubernetes": _ok_transport}, ledger=led,
                 locks=LockTable(), dry_run=True,
                 preconditions={"observation": OBS,
                                "current_plan_hash": env.change_plan_hash})
    assert r1["ok"] and op.state == "verifying"
    from platformforge.ops.engine import finalize_verify
    finalize_verify(op, led, {"convergence": "converged"})
    assert op.state == "converged"
    # replay — converged is terminal for execution
    r2 = execute(op, env, approvals=[ap],
                 transports={"kubernetes": _ok_transport}, ledger=led,
                 locks=LockTable(), dry_run=True,
                 preconditions={"observation": OBS,
                                "current_plan_hash": env.change_plan_hash})
    assert not r2["ok"]


def test_idempotent_step_not_repeated():
    env = _env()
    env.actions.append({"step_id": "s1b", "action": "kubernetes.scale",
                        "params": {"kind": "Deployment", "name": "w",
                                   "namespace": "apps", "replicas": 3}})
    h = env.freeze()
    ap = Approval(subject_hash=h, scope=list(env.scope), actor="alice")
    calls = []
    def t(argv, cwd=None, timeout_s=None):
        calls.append(argv)
        return 0, "ok", ""
    led = OperationLedger()
    execute(Operation(operation_id="op", resources=list(env.scope)),
            env, approvals=[ap], transports={"kubernetes": t},
            ledger=led, locks=LockTable(), dry_run=True,
            preconditions={"observation": OBS,
                           "current_plan_hash": env.change_plan_hash})
    skipped = [e for e in led.entries if e.event == "step.skipped"]
    assert skipped and "idempotent" in skipped[0].data["reason"]


def test_ledger_redacts_secrets():
    led = OperationLedger()
    led.append("test", "op1", data={
        "note": "token: ghp_1234567890abcdefghijkl"})
    assert "ghp_" not in json.dumps(led.to_dict())
    assert "REDACTED" in json.dumps(led.to_dict())


def test_envelope_to_dict_redacts_secret_params():
    env = _env()
    env.actions[0]["params"]["note"] = \
        "api_key = abcdefgh12345678ijklmnop"
    blob = json.dumps(env.to_dict())
    assert "abcdefgh12345678ijklmnop" not in blob


def test_ledger_tamper_breaks_chain():
    led = OperationLedger()
    led.append("a", "op1")
    led.append("b", "op1")
    led.entries[0].data["injected"] = True   # attacker edit
    assert not led.verify_chain()


def test_unknown_risk_is_not_low():
    a = assess("some.unknown_action", {}, {"environment": "prod"})
    assert a.risk_class in ("R4", "R5")


def test_policy_deny_survives_serialization():
    """Deny decision survives context compression — serialize → dict →
    the effective field still denies."""
    from platformforge.ops.policy import Policy, evaluate
    d = evaluate({"environment": "prod"},
                 [Policy(policy_id="d", priority=1,
                         when={"environment": "prod"},
                         then={"decision": "deny"})])
    blob = json.loads(json.dumps(d.to_dict()))
    assert blob["decision"] == "deny" and blob["effective"] == "deny"


def test_shadow_policy_never_enforces():
    from platformforge.ops.policy import Policy, evaluate
    d = evaluate({"environment": "prod"},
                 [Policy(policy_id="s", shadow=True,
                         when={"environment": "prod"},
                         then={"decision": "deny"})])
    assert d.effective == "would_deny"
    assert d.decision == "deny"


def test_break_glass_still_audited():
    env = _env()
    led = OperationLedger()
    bg = BreakGlass(break_glass_id="BG-1", actor="oncall",
                    invocation_reason="sev1", scope=list(env.scope),
                    expires_at="2999-01-01T00:00:00Z")
    r = execute(Operation(operation_id="op", resources=list(env.scope)),
                env, approvals=[], break_glass=bg,
                transports={"kubernetes": _ok_transport},
                ledger=led, locks=LockTable(), dry_run=True,
                preconditions={"observation": OBS,
                               "current_plan_hash": env.change_plan_hash})
    assert r["ok"] and led.verify_chain()
    assert led.entries          # every step recorded
