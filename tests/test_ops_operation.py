"""Phase F gates — operation FSM, hash-chained ledger, locks, resume,
idempotency, preconditions."""

from platformforge.ops.operation import (
    ExecutionStep,
    LockTable,
    Operation,
    OperationLedger,
    dedup_check,
    resume,
)
from platformforge.ops.preconditions import check_preconditions


def _ledger():
    return OperationLedger()


def test_valid_transition_chain():
    led = _ledger()
    op = Operation(operation_id="op1", plan_hash="sha256:p")
    assert op.transition("planned", led)["ok"]
    assert op.transition("simulated", led)["ok"]
    assert op.transition("policy-reviewed", led)["ok"]
    assert op.transition("awaiting-approval", led)["ok"]
    assert op.transition("approved", led)["ok"]
    assert op.transition("executing", led)["ok"]
    assert op.transition("verifying", led)["ok"]
    assert op.transition("converged", led)["ok"]
    assert op.state == "converged"
    assert len(led.for_operation("op1")) == 8


def test_invalid_transition_refuses():
    led = _ledger()
    op = Operation(operation_id="op2")
    r = op.transition("executing", led)
    assert r["refusal"] == "PF-OPS-BAD-TRANSITION"
    assert "draft" in r["unlock"]


def test_ledger_hash_chain_tamper_evidence():
    led = _ledger()
    led.append("intent.created", "op1", actor="human")
    led.append("plan.created", "op1", data={"hash": "x"})
    assert led.verify_chain()
    led.entries[0].data["injected"] = True
    assert not led.verify_chain()


def test_actor_kinds_enforced():
    led = _ledger()
    e = led.append("x", "op", actor="not-a-thing")
    assert e.actor == "system"


def test_lock_conflict_blocks():
    lt = LockTable()
    led = _ledger()
    assert lt.acquire(["r1"], "op-a", led)["ok"]
    r = lt.acquire(["r1", "r2"], "op-b", led)
    assert r["refusal"] == "PF-OPS-LOCK-CONFLICT"
    lt.release("op-a", led)
    assert lt.acquire(["r1", "r2"], "op-b", led)["ok"]


def test_idempotency_key_deterministic():
    s = ExecutionStep(step_id="s1", action="git.apply_patch",
                      params={"patch": "abc"})
    assert s.key("sha256:p") == s.key("sha256:p")
    seen = set()
    assert dedup_check(seen, s.key("sha256:p"))
    assert not dedup_check(seen, s.key("sha256:p"))


def test_resume_replays_ledger():
    led = _ledger()
    op = Operation(operation_id="op9",
                   steps=[ExecutionStep(step_id="a", action="x"),
                          ExecutionStep(step_id="b", action="y")])
    op.state = "executing"
    led.append("step.completed", "op9", data={"step_id": "a"})
    r = resume(op, led)
    assert r["completed_steps"] == ["a"]
    assert r["pending_steps"] == ["b"]
    assert "revalidate-approval" in r["requires"]


def test_precondition_stale_observation_fails():
    r = check_preconditions(
        observation={"captured_at": "2020-01-01T00:00:00Z",
                     "coverage": {"complete": True}},
        max_observation_age_s=900)
    assert not r["ok"]
    assert r["refusal"]["refusal"] == "PF-OPS-PRECONDITION-FAILED"
    assert "observation-fresh" in r["refusal"]["failed"]


def test_precondition_plan_hash_mismatch():
    r = check_preconditions(
        observation={"captured_at": "2999-01-01T00:00:00Z",
                     "coverage": {"complete": True}},
        plan_hash="sha256:a", current_plan_hash="sha256:b")
    assert not r["ok"]
    assert "plan-still-valid" in r["refusal"]["failed"]


def test_precondition_freeze_requires_break_glass():
    base = {"observation": {"captured_at": "2999-01-01T00:00:00Z",
                            "coverage": {"complete": True}},
            "freeze_active": True}
    assert not check_preconditions(**base)["ok"]
    assert check_preconditions(**base, break_glass=True)["ok"]


def test_precondition_all_green():
    r = check_preconditions(
        observation={"captured_at": "2999-01-01T00:00:00Z",
                     "coverage": {"complete": True}},
        expected_resource_state={"a": 1},
        current_resource_state={"a": 1},
        plan_hash="sha256:a", current_plan_hash="sha256:a",
        owner="team", current_owner="team",
        policy_decision="allow", approval_valid=True)
    assert r["ok"]
