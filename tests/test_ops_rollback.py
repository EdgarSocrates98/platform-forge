"""Phase L gates — rollback plan model, strategy derivation, saga."""

from platformforge.ops.rollback import RollbackPlan, compensate_for, derive_rollback


def test_scale_rollback_is_previous_replicas():
    plan = derive_rollback(
        [{"action": "kubernetes.scale",
          "params": {"kind": "Deployment", "name": "w", "replicas": 5}}],
        {"previous_replicas": 3, "environment": "dev"})
    assert plan.strategy == "previous-artifact"
    inv = plan.actions[0]
    assert inv["action"] == "kubernetes.scale"
    assert inv["params"]["replicas"] == 3


def test_terraform_revert():
    p = derive_rollback(
        [{"action": "terraform.apply_saved_plan",
          "params": {"workdir": "/w", "plan_file": "p"}}], {})
    assert p.strategy == "terraform-revert"


def test_auto_rollback_disabled_in_prod():
    p = derive_rollback(
        [{"action": "kubernetes.rollout_restart",
          "params": {"kind": "Deployment", "name": "w"}}],
        {"environment": "prod", "automatic_allowed": True})
    assert not p.automatic
    assert any("prod" in l for l in p.limitations)


def test_unknown_rollback_flagged():
    p = RollbackPlan(strategy="unknown")
    codes = {v["refusal"] for v in p.validate()}
    assert "PF-OPS-ROLLBACK-UNKNOWN" in codes


def test_manual_only_cannot_be_automatic():
    p = RollbackPlan(strategy="manual-only", automatic=True)
    codes = {v["refusal"] for v in p.validate()}
    assert "PF-OPS-ROLLBACK-CONTRADICTION" in codes


def test_saga_reverse_order():
    steps = [
        {"step_id": "s1", "action": "git.create_branch", "status": "completed",
         "params": {"repo": "r", "branch": "b"}},
        {"step_id": "s2", "action": "kubernetes.scale", "status": "completed",
         "params": {"kind": "Deployment", "name": "w", "replicas": 5}},
        {"step_id": "s3", "action": "terraform.apply_saved_plan",
         "status": "failed", "params": {}}]
    r = compensate_for(steps)
    assert r["compensating_actions"][0]["action"] == "kubernetes.scale"
    assert r["compensating_actions"][1]["action"] == "git.delete_branch"
    assert r["compensating_actions"][1]["compensates"] == "s1"


def test_mixed_actions_compensating_strategy():
    p = derive_rollback([
        {"action": "git.open_pr", "params": {}},
        {"action": "kubernetes.scale",
         "params": {"kind": "Deployment", "name": "w", "replicas": 3}}], {})
    assert p.strategy in ("compensating", "git-revert")
    assert len(p.actions) == 2
