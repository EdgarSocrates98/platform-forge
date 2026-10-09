"""Rollback plan model v2 — strategies, statuses, material binding,
saga compensation (Cycle 4.1 §21–43)."""

from platformforge.live.models import canonical_hash
from platformforge.ops.material import MaterialStore, capture_material
from platformforge.ops.rollback import (
    RollbackPlan,
    build_rollback_plan,
    compensate_for,
    derive_rollback,
    terraform_plan_reuse_check,
)


def _mat(action="kubernetes.scale", sid="s1", pre=None, exe=None,
         params=None):
    m = capture_material(action, sid, "op1", params or {},
                         required=("replicas",) if action ==
                         "kubernetes.scale" else (),
                         pre_state=pre if pre is not None
                         else {"replicas": 3, "resource_version": "v1"})
    m.execution_result.update(exe or {})
    return m


def test_scale_rollback_uses_captured_material():
    """§12/§31 — replicas come from captured pre-state, never from
    copied forward params."""
    mat = _mat(pre={"replicas": 3, "resource_version": "rv-9"})
    plan = build_rollback_plan(
        [{"step_id": "s1", "action": "kubernetes.scale",
          "params": {"kind": "Deployment", "name": "w", "replicas": 5}}],
        materials={"s1": mat})
    assert plan.strategy == "direct-inverse"
    assert plan.status == "executable"
    inv = plan.actions[0]
    assert inv["action"] == "kubernetes.scale"
    assert inv["params"]["replicas"] == 3
    assert inv["material_hash"] == mat.hash()


def test_scale_without_material_is_unresolved():
    plan = build_rollback_plan(
        [{"step_id": "s1", "action": "kubernetes.scale",
          "params": {"kind": "Deployment", "name": "w", "replicas": 5}}])
    assert plan.status == "unresolved"
    assert plan.actions == []
    assert any("missing pre-state" in l for l in plan.limitations)


def test_terraform_forward_plan_never_a_rollback_plan():
    """§15–19 — apply_saved_plan is replan-required; the saved forward
    plan is never reused as the reverse plan."""
    p = build_rollback_plan(
        [{"step_id": "s1", "action": "terraform.apply_saved_plan",
          "params": {"workdir": "/w", "plan_file": "p.tfplan",
                     "plan_hash": "sha256:fwd",
                     "source_ref": "main", "workspace": "default",
                     "state_serial": "7",
                     "resource_addresses": ["aws_s3_bucket.b"]}}],
        materials={"s1": _mat("terraform.apply_saved_plan",
                              pre={"source_ref": "main",
                                   "workspace": "default",
                                   "state_serial": "7",
                                   "resource_addresses":
                                       ["aws_s3_bucket.b"]})})
    assert p.strategy == "replan-required"
    assert p.status == "requires-replan"
    assert p.replans and p.replans[0]["source_ref"] == "main"
    assert p.replans[0]["forward_plan_hash"] == "sha256:fwd"
    assert terraform_plan_reuse_check("sha256:fwd", "sha256:fwd")[
        "refusal"] == "PF-OPS-PLAN-REUSE"
    assert terraform_plan_reuse_check("sha256:fwd", "sha256:back") is None


def test_argocd_rollback_requires_history():
    """§22 — argo rollback without a captured history id is not
    executable."""
    p = build_rollback_plan(
        [{"step_id": "s1", "action": "argocd.sync",
          "params": {"app": "shop"}}],
        materials={"s1": _mat("argocd.sync", pre={})})
    assert p.status == "unresolved"
    assert any("missing pre-state" in l for l in p.limitations)
    mat = _mat("argocd.sync",
               pre={"history_id": "42", "previous_revision": "rev-a",
                    "repo": "git@x"})
    p2 = build_rollback_plan(
        [{"step_id": "s1", "action": "argocd.sync",
          "params": {"app": "shop"}}], materials={"s1": mat})
    assert p2.status == "executable"
    assert p2.actions[0]["params"]["history_id"] == "42"


def test_annotate_absent_vs_previous_value():
    """§12 — an annotation that was absent must be REMOVED on rollback,
    not restored to a phantom value."""
    absent = _mat("kubernetes.annotate", pre={"annotations": {}})
    p = build_rollback_plan(
        [{"step_id": "s1", "action": "kubernetes.annotate",
          "params": {"kind": "Deployment", "name": "w",
                     "annotations": {"team": "a"}}}],
        materials={"s1": absent})
    assert p.status == "executable"
    assert p.actions[0]["params"].get("remove_annotations") == ["team"]
    prev = _mat("kubernetes.annotate",
                pre={"annotations": {"team": "old"}})
    p2 = build_rollback_plan(
        [{"step_id": "s1", "action": "kubernetes.annotate",
          "params": {"kind": "Deployment", "name": "w",
                     "annotations": {"team": "a"}}}],
        materials={"s1": prev})
    assert p2.actions[0]["params"]["annotations"] == {"team": "old"}


def test_derive_rollback_declares_but_does_not_claim():
    """At mint time (no materials yet) the plan stays unresolved —
    'rollback ready' is only claimed once material exists (§37)."""
    p = derive_rollback(
        [{"step_id": "s1", "action": "kubernetes.scale",
          "params": {"kind": "Deployment", "name": "w", "replicas": 5}}],
        {"environment": "dev"})
    assert p.strategy == "direct-inverse"
    assert p.status == "unresolved"


def test_auto_rollback_disabled_in_prod():
    mat = _mat()
    p = build_rollback_plan(
        [{"step_id": "s1", "action": "kubernetes.scale",
          "params": {"kind": "Deployment", "name": "w", "replicas": 5}}],
        materials={"s1": mat},
        context={"environment": "prod", "automatic_allowed": True})
    assert p.status == "executable"
    assert not p.automatic
    assert any("prod" in l for l in p.limitations)


def test_unknown_rollback_flagged():
    p = RollbackPlan(strategy="bogus-strategy")
    codes = {v["refusal"] for v in p.validate()}
    assert "PF-OPS-BAD-ROLLBACK-TYPE" in codes


def test_manual_only_cannot_be_automatic():
    p = RollbackPlan(strategy="manual-only", status="manual-only",
                     automatic=True)
    codes = {v["refusal"] for v in p.validate()}
    assert "PF-OPS-ROLLBACK-CONTRADICTION" in codes


def test_material_is_immutable_and_hash_bound(tmp_path):
    mat = _mat()
    h1 = mat.hash()
    store = MaterialStore(tmp_path / "mats")
    assert store.put(mat)["ok"] is True
    mat.pre_state["replicas"] = 99       # tamper after capture
    assert mat.hash() != h1
    # same hash-path write with different content → tamper refusal
    mat.material_id = "mat-forged"
    out = store.put(mat)
    # forged content lands at a DIFFERENT hash path (content-addressed)
    assert out["ok"] is True
    assert out["hash"] != h1
    # the stored original is untouched and verifies
    got = store.get(h1)
    assert got is not None and got.pre_state["replicas"] == 3
    assert got.hash() == h1 == "sha256:" + canonical_hash(got.payload())


def test_saga_reverse_order():
    mats = {"s2": _mat(pre={"replicas": 3}),
            "s1": _mat("git.create_branch", sid="s1", pre={})}
    steps = [
        {"step_id": "s1", "action": "git.create_branch", "status": "completed",
         "params": {"repo": "r", "branch": "b"}},
        {"step_id": "s2", "action": "kubernetes.scale", "status": "completed",
         "params": {"kind": "Deployment", "name": "w", "replicas": 5}},
        {"step_id": "s3", "action": "terraform.apply_saved_plan",
         "status": "failed", "params": {}}]
    r = compensate_for(steps, materials=mats)
    assert r["compensating_actions"][0]["action"] == "kubernetes.scale"
    assert r["compensating_actions"][0]["params"]["replicas"] == 3
    assert r["compensating_actions"][1]["action"] == "git.delete_branch"
    assert r["compensating_actions"][1]["compensates"] == "s1"


def test_mixed_actions_worst_status_wins():
    mats = {"s1": _mat(), "s2": _mat("git.open_pr", sid="s2",
                                     pre={}, exe={"pr": 7})}
    p = build_rollback_plan([
        {"step_id": "s2", "action": "git.open_pr", "params": {"repo": "r"}},
        {"step_id": "s1", "action": "kubernetes.scale",
         "params": {"kind": "Deployment", "name": "w", "replicas": 3}}],
        materials=mats)
    assert p.status == "executable"
    assert len(p.actions) == 2
    # manual-only step degrades the whole plan
    p2 = build_rollback_plan([
        {"step_id": "s1", "action": "kubernetes.scale",
         "params": {"kind": "Deployment", "name": "w", "replicas": 3}},
        {"step_id": "s9", "action": "git.push",
         "params": {"repo": "r", "branch": "b"}}],
        materials={"s1": _mat()})
    assert p2.status == "manual-only"
