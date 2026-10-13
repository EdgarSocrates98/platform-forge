"""Cycle 4.1 §123–127 — runbook safe rollback references."""

from platformforge.ops.material import capture_material
from platformforge.ops.runbook import BUILTIN_RUNBOOKS, Runbook, bind_params, resolve_ref


def test_resolve_ref_allowlisted_only():
    ctx = {"pre_state": {"replicas": 3}, "params": {"replicas": 5}}
    assert resolve_ref({"from": "pre_state.replicas"}, ctx) == {
        "ok": True, "value": 3}
    r = resolve_ref({"from": "os.environ"}, ctx)
    assert r["refusal"] == "PF-OPS-RUNBOOK-BAD-REF"
    r = resolve_ref({"from": "pre_state.nonexistent"}, ctx)
    assert r["refusal"] == "PF-OPS-RUNBOOK-REF-MISSING"


def test_bind_params_mixed_literals_and_refs():
    ctx = {"pre_state": {"replicas": 3, "annotations": {"a": "b"}}}
    r = bind_params({"replicas": {"from": "pre_state.replicas"},
                     "namespace": "default"}, ctx)
    assert r["ok"] and r["params"] == {"replicas": 3,
                                       "namespace": "default"}


def test_bind_rollback_uses_captured_state_not_forward_params():
    mat = capture_material("kubernetes.scale", "scale", "op1",
                           {"replicas": 5, "current_replicas": 3},
                           {"replicas"},
                           pre_state={"replicas": 3})
    rb = BUILTIN_RUNBOOKS["scale-out-under-pressure"]
    out = rb.bind_rollback({"scale": mat},
                           forward_params={"replicas": 5})
    assert out["ok"]
    # the rollback restores 3 — never reuses the forward param 5
    assert out["actions"][0]["params"]["replicas"] == 3
    assert out["actions"][0]["for_step"] == "scale"


def test_bind_rollback_missing_material_refuses():
    rb = BUILTIN_RUNBOOKS["scale-out-under-pressure"]
    out = rb.bind_rollback({"scale": {"pre_state": {}}})
    assert not out["ok"]
    assert out["refusal"]["refusal"] == "PF-OPS-RUNBOOK-REF-MISSING"


def test_audit_flags_bad_ref_root_and_unknown_rollback_action():
    rb = Runbook(runbook_id="x", title="t",
                 trigger={"a": 1}, sources=["s"],
                 rollback={"actions": [{
                     "action": "shell.run",
                     "params": {"x": {"from": "env.HOME"}}}]})
    codes = {v["refusal"] for v in rb.audit()}
    assert "PF-OPS-UNKNOWN-ACTION" in codes
    assert "PF-OPS-RUNBOOK-BAD-REF" in codes
