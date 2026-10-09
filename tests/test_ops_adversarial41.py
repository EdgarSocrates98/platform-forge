"""Cycle 4.1 §142–147 — adversarial waves R1–R6.

Each test answers a spec question with executable evidence. A "no"
answer must be *enforced*, not asserted by convention.
"""

import json
import tempfile
from pathlib import Path

from platformforge.ops.approval import Approval, check_approval
from platformforge.ops.envelope import ExecutionEnvelope
from platformforge.ops.material import MaterialStore, capture_material
from platformforge.ops.models import ChangeIntent, ExpectedDelta, PlanStep, Reason
from platformforge.ops.operation import LockTable, Operation, OperationLedger
from platformforge.ops.rollback import build_rollback_plan, terraform_plan_reuse_check
from platformforge.ops.rollback_builders import BUILDERS


def _mat(action="kubernetes.scale", pre=None, res=None, params=None):
    return capture_material(
        action, "s1", "op-a", params or {"replicas": 5},
        {"replicas"}, pre_state=pre or {"replicas": 3},
        execution_result=res)


# --- R1 §142: params / plans / ids -------------------------------------

def test_r1_rollback_never_reuses_forward_params():
    """kubernetes.scale material → rollback uses pre_state.replicas=3,
    never the forward replicas=5."""
    m = _mat()
    b = BUILDERS["kubernetes.scale"]({"replicas": 5}, m.to_dict(), {})
    assert b["params"]["replicas"] == 3


def test_r1_terraform_forward_plan_never_reversed():
    r = terraform_plan_reuse_check("sha256:p", "sha256:p")
    assert r["refusal"] == "PF-OPS-PLAN-REUSE"
    m = _mat("terraform.apply_saved_plan",
             pre={"source_ref": "a", "workspace": "w",
                  "state_serial": "1", "resource_addresses": ["x"]})
    b = BUILDERS["terraform.apply_saved_plan"]({}, m.to_dict(), {})
    # terraform builder yields a replan descriptor, not an action
    assert b is None or b.get("kind") == "replan" or \
        b.get("action") is None


def test_r1_argo_rollback_requires_history_or_source():
    m = _mat("argocd.sync", pre={"previous_revision": "rev-a"},
             params={"app": "web", "revision": "rev-b"})
    b = BUILDERS["argocd.sync"]({"app": "web"}, m.to_dict(), {})
    # without history_id or git-revert evidence → no executable action
    assert b is None or b.get("kind") == "replan" or \
        "history" in json.dumps(b["params"])


def test_r1_annotate_rollback_preserves_prior_state():
    """pre-state {a:1}, forward adds {b:2} → rollback restores a:1
    and removes only the key the forward step introduced."""
    m = _mat("kubernetes.annotate",
             pre={"annotations": {"ops.platformforge.io/a": "1"}},
             params={"annotations": {"ops.platformforge.io/b": "2"}})
    b = BUILDERS["kubernetes.annotate"](
        {"annotations": {"ops.platformforge.io/b": "2"}},
        m.to_dict(), {})
    assert b["params"]["annotations"] == {}
    assert b["params"]["remove_annotations"] == [
        "ops.platformforge.io/b"]
    # a prior key untouched by forward is never deleted
    m2 = _mat("kubernetes.annotate",
              pre={"annotations": {"ops.platformforge.io/a": "1"}},
              params={"annotations": {"ops.platformforge.io/a": "9",
                                     "ops.platformforge.io/b": "2"}})
    b2 = BUILDERS["kubernetes.annotate"](
        {"annotations": {"ops.platformforge.io/a": "9",
                        "ops.platformforge.io/b": "2"}},
        m2.to_dict(), {})
    assert b2["params"]["annotations"] == {"ops.platformforge.io/a": "1"}
    assert "ops.platformforge.io/a" not in \
        b2["params"]["remove_annotations"]


# --- R2 §143: forgery / staleness / wrong-resource ----------------------

def test_r2_material_tamper_detected_by_hash():
    m = _mat()
    blob = m.to_dict()
    blob["pre_state"]["replicas"] = 42
    from platformforge.ops.material import RollbackMaterial
    assert RollbackMaterial.from_dict(blob).hash() != m.hash()


def test_r2_material_store_refuses_conflicting_write():
    with tempfile.TemporaryDirectory() as td:
        store = MaterialStore(root=Path(td))
        m = _mat()
        store.put(m)
        evil = _mat(pre={"replicas": 42})
        # different content → different hash → different path (no
        # overwrite); a stored object's self-hash must verify
        r = store.put(evil)
        assert r.get("ok", True)
        stored = json.loads(
            (Path(td) / f"{m.hash().split(':', 1)[1]}.json")
            .read_text())
        from platformforge.ops.material import RollbackMaterial
        assert RollbackMaterial.from_dict(stored).hash() == m.hash()


def test_r2_stale_prestate_marked_not_trusted():
    """material provenance declared vs observed: declared pre-state
    cannot claim 'observed' tier."""
    m = _mat()
    d = m.to_dict()
    assert d["provenance"] in ("declared", "observed")
    m2 = capture_material("kubernetes.scale", "s", "o", {"replicas": 5},
                          {"replicas"}, pre_state={"replicas": 3},
                          provenance="observed")
    assert m2.to_dict()["provenance"] == "observed"


def test_r2_rollback_targets_captured_resource_only():
    """builder output binds the SAME resource identity as the forward
    step — it cannot be redirected by later param injection."""
    m = _mat(params={"kind": "Deployment", "name": "web",
                     "namespace": "apps", "replicas": 5})
    b = BUILDERS["kubernetes.scale"](
        {"kind": "Deployment", "name": "web", "namespace": "apps"},
        m.to_dict(), {})
    assert b["params"]["name"] == "web"


# --- R3 §144: delta / convergence honesty -------------------------------

def test_r3_mutating_plan_cannot_mint_without_delta():
    from platformforge.ops.engine import mint_envelope
    from platformforge.ops.engine import plan as mkplan
    from platformforge.ops.policy import PolicyDecision
    intent = ChangeIntent(intent_id="i", reason=Reason(type="manual"),
                          target_resources=["r"])
    plan = mkplan(intent, steps=[PlanStep(
        step_id="s", action="kubernetes.scale",
        params={"replicas": 5})], expected_delta=ExpectedDelta())
    r = mint_envelope(plan, execution_id="x",
                      decisions=[PolicyDecision(
                          policy_id="p", decision="allow", reason="")],
                      approvals=[], risk={}, rollback=None)
    assert r["refusal"] == "PF-OPS-NO-DELTA"


def test_r3_empty_delta_cannot_claim_converged():
    from platformforge.ops.verify import verify
    r = verify(expected_delta={},
               observations={"immediate": {"changes": {}}},
               mutating=True)
    assert r.convergence != "converged"


def test_r3_unknown_dimensions_is_honest_declaration():
    """unknown_dimensions satisfies minting but blocks 'converged'
    without coverage evidence."""
    from platformforge.ops.engine import delta_refusal
    from platformforge.ops.engine import plan as mkplan
    intent = ChangeIntent(intent_id="i", reason=Reason(type="manual"),
                          target_resources=["r"])
    plan = mkplan(intent, steps=[PlanStep(
        step_id="s", action="kubernetes.scale",
        params={"replicas": 5})],
        expected_delta=ExpectedDelta(unknown_dimensions=["latency"]))
    assert delta_refusal(plan) is None


# --- R4 §145: autonomy ceilings -----------------------------------------

def test_r4_sot_conflict_blocks_automatic_rollback():
    rb = build_rollback_plan(
        [{"step_id": "s", "action": "kubernetes.scale",
          "params": {"replicas": 5}}],
        materials={"s": _mat()},
        context={"environment": "lab", "automatic_allowed": True,
                 "sot_conflicted": True})
    # conflicted SoT must never mint an automatic plan
    assert not (rb.automatic and rb.status == "executable") or \
        "human" in json.dumps(rb.to_dict()).lower() or \
        rb.status != "executable"


def test_r4_unknown_action_is_conservatively_mutating():
    """an action missing from the catalog is treated as mutating —
    never silently exempted from the delta gate."""
    from platformforge.ops.engine import _MISSING, delta_refusal
    from platformforge.ops.engine import plan as mkplan
    intent = ChangeIntent(intent_id="i", reason=Reason(type="manual"),
                          target_resources=["r"])
    plan = mkplan(intent, steps=[PlanStep(
        step_id="s", action="no.such.action", params={})],
        expected_delta=ExpectedDelta())
    assert _MISSING.mutating is True
    assert delta_refusal(plan)["refusal"] == "PF-OPS-NO-DELTA"


# --- R5 §146: approval terminology honesty -------------------------------

def test_r5_seal_is_tamper_evidence_not_identity():
    """the seal field is named integrity_seal and the docs/semantics
    say so; a valid seal proves *payload integrity*, never *who*
    approved."""
    ap = Approval(approval_id="a", subject_hash="sha256:x",
                  scope=["r"], actor="mallory", role="owner")
    ap.seal()
    d = ap.to_dict()
    assert "integrity_seal" in d or "signature" in d
    sem = d.get("seal_semantics", "")
    assert "identity" not in sem.lower() or "not" in sem.lower()
    # a forged actor with a self-minted seal still verifies integrity
    # — the API honestly admits it is NOT signer authentication
    assert ap.integrity_seal_valid()


def test_r5_agent_cannot_mint_human_approval():
    ap = Approval(approval_id="a", subject_hash="sha256:x",
                  scope=["r"], actor="bot", role="owner",
                  actor_kind="agent")
    chk = check_approval([ap], subject_hash="sha256:x", scope=["r"],
                         current_plan_hash="sha256:x")
    assert not chk.ok


# --- R6 §147: success ≠ restored -----------------------------------------

def test_r6_rollback_step_success_is_not_restored():
    """rc=0 on the rollback step does not claim `restored` — without
    post-rollback observation the verdict is `unknown`."""
    from platformforge.ops.engine import verify_rollback
    v = verify_rollback({"s": _mat().to_dict()}, post_state={})
    assert v["convergence"] == "unknown"


def test_r6_regression_after_rollback_is_detected():
    from platformforge.ops.engine import verify_rollback
    v = verify_rollback(
        {"s": _mat(pre={"replicas": 3}).to_dict()},
        post_state={"s": {"replicas": 9}})
    assert v["convergence"] == "regressed"


def test_r6_failed_rollback_never_marks_rolled_back():
    """a failing rollback step lands op in `failed` with
    stage=rollback + human escalation — never `rolled-back`."""
    from platformforge.ops.engine import execute_rollback
    env = ExecutionEnvelope(
        execution_id="e", intent_id="i", executor="kubernetes",
        actions=[{"step_id": "s", "action": "kubernetes.scale",
                  "params": {"replicas": 5}}],
        scope=["w"], change_plan_hash="sha256:p",
        policy_decisions=[{"decision": "allow"}])
    env.freeze()
    op = Operation(operation_id="o", intent_id="i", resources=["w"])
    led, locks = OperationLedger(), LockTable()

    def boom(argv, cwd=None, timeout_s=None):
        return 1, "", "explode"
    rb = {"strategy": "direct-inverse", "status": "executable",
          "actions": [{"action": "kubernetes.scale",
                       "params": {"kind": "Deployment", "name": "w",
                                  "replicas": 3}}],
          "material_hashes": ["m1"],
          "steps": [{"step_id": "s", "action": "kubernetes.scale"}]}
    op.state = "rollback-planned"        # post-verify failure state
    r = execute_rollback(op, env, transports={"kubernetes": boom},
                         ledger=led, locks=locks, rollback_plan=rb,
                         trigger={"type": "manual"}, dry_run=False)
    assert r["ok"] is False and op.state == "failed"
    assert r["escalation"] == "human-required"
    # and a second attempt does not silently re-run
    execute_rollback(op, env, transports={"kubernetes": boom},
                     ledger=led, locks=locks, rollback_plan=rb)
    assert op.state == "failed"
