"""Phase G–M gates — envelope, typed actions, executor boundary."""

import pytest

from platformforge.ops.actions import FORBIDDEN_ACTIONS, catalog, spec_for, validate_action
from platformforge.ops.envelope import ExecutionEnvelope
from platformforge.ops.executors.git import GitExecutor, pr_body
from platformforge.ops.executors.gitops import ArgoCDExecutor, KubernetesExecutor
from platformforge.ops.executors.terraform import TerraformExecutor, TofuExecutor, summarize_plan


def _env(**kw):
    base = {"execution_id": "ex1", "intent_id": "i1",
            "change_plan_hash": "sha256:p", "executor": "git",
            "actions": [{"action": "git.apply_patch",
                         "params": {"repo": ".", "patch": "x"}}],
            "scope": ["r1"], "approvals": ["a1"]}
    base.update(kw)
    return ExecutionEnvelope(**base)


def test_no_shell_action_exists():
    assert spec_for("shell.run") is None
    for a in FORBIDDEN_ACTIONS:
        r = validate_action(a, {})
        assert r["refusal"] == "PF-OPS-UNSTRUCTURED"


def test_action_param_validation():
    assert validate_action("kubernetes.scale", {"kind": "Deployment",
                            "name": "w", "replicas": 3}) is None
    r = validate_action("kubernetes.scale", {"kind": "Deployment"})
    assert r["refusal"] == "PF-OPS-ACTION-PARAMS"
    r2 = validate_action("git.open_pr", {"repo": "r", "title": "t",
                         "head": "h", "base": "b", "body": "x",
                         "evil_param": "rm -rf"})
    assert r2["refusal"] == "PF-OPS-ACTION-PARAMS"


def test_envelope_requires_governance():
    v = _env(approvals=[], policy_decisions=[]).validate()
    assert any(x["refusal"] == "PF-OPS-ENVELOPE-UNGOVERNED" for x in v)


def test_envelope_immutable_after_freeze():
    e = _env()
    h = e.freeze()
    assert e.is_intact()
    e.actions.append({"action": "git.commit", "params": {"repo": ".",
                                                       "message": "x"}})
    assert not e.is_intact()
    assert e.hash() != h


def test_envelope_hash_deterministic():
    assert _env(created_at="t").hash() == _env(created_at="t").hash()


def test_executor_rejects_foreign_action():
    g = GitExecutor()
    r = g.run_step("s1", "kubernetes.scale",
                   {"kind": "Deployment", "name": "w", "replicas": 3},
                   transport=lambda *a: (0, "", ""))
    assert not r.ok
    assert r.refusal["refusal"] == "PF-OPS-WRONG-EXECUTOR"


def test_mutating_action_needs_transport():
    g = GitExecutor()
    r = g.run_step("s1", "git.commit", {"repo": ".", "message": "m"})
    assert r.refusal["refusal"] == "PF-OPS-NO-TRANSPORT"


def test_git_executor_argv():
    g = GitExecutor()
    calls = []
    r = g.run_step("s1", "git.create_branch",
                   {"repo": "/r", "branch": "pf/op1", "base": "main"},
                   transport=lambda a, c, t: (calls.append(a), (0, "", ""))[1])
    assert r.ok and calls[0][:4] == ["git", "-C", "/r", "checkout"]


def test_kubectl_scale_argv_with_preconditions():
    k = KubernetesExecutor()
    argv = k.argv_for("kubernetes.scale",
                      {"kind": "Deployment", "name": "web",
                       "namespace": "prod", "replicas": 5,
                       "current_replicas": 3, "resource_version": "42"},
                      False)
    assert "--current-replicas" in argv and "--resource-version" in argv
    assert argv[:3] == ["kubectl", "scale", "Deployment/web"]


def test_annotate_whitelist_blocks_foreign():
    k = KubernetesExecutor()
    r = k.argv_for("kubernetes.annotate",
                   {"kind": "Deployment", "name": "w",
                    "annotations": {"evil.io/x": "y"}}, False)
    assert r["refusal"] == "PF-OPS-ANNOTATE-UNSAFE"


def test_annotate_resourceversion_uses_json_test_patch():
    k = KubernetesExecutor()
    argv = k.argv_for("kubernetes.annotate",
                      {"kind": "Deployment", "name": "w",
                       "annotations": {"platformforge.io/note": "x"},
                       "resource_version": "7"}, False)
    assert argv[:2] == ["kubectl", "patch"]
    assert '"op":"test"' in argv[5]


def test_terraform_plan_then_apply_contract():
    t = TerraformExecutor()
    assert "apply" in t.argv_for(
        "terraform.apply_saved_plan",
        {"workdir": "/w", "plan_file": "p.tfplan"}, False)
    # hash mismatch refuses before any argv
    r = t.argv_for("terraform.apply_saved_plan",
                   {"workdir": "/nope", "plan_file": "none",
                    "plan_hash": "sha256:deadbeef"}, False)
    assert r["refusal"] == "PF-OPS-PLAN-UNREADABLE"


def test_argocd_sync_never_prunes():
    a = ArgoCDExecutor()
    argv = a.argv_for("argocd.sync", {"app": "web"}, True)
    assert "--dry-run" in argv
    assert "--prune" not in argv and "--force" not in argv
    assert "--replace" not in argv


def test_tofu_parity():
    assert TofuExecutor().argv_for("tofu.plan", {"workdir": "/w"},
                                   True)[0] == "tofu"


def test_summarize_plan():
    s = summarize_plan({"applyable": True, "resource_changes": [
        {"address": "aws_vpc.a", "change": {"actions": ["create"]}},
        {"address": "aws_db.b", "change": {"actions": ["delete", "create"]}}],
        "resource_drift": [{"address": "aws_s3.c"}]})
    assert s["actions"] == {"create": 2, "delete": 1}
    assert s["destructive_addresses"] == ["aws_db.b"]
    assert s["drift"] == ["aws_s3.c"]


def test_pr_body_has_evidence():
    body = pr_body(reason="fix", evidence=["f1"], plan_hash="sha256:x",
                   expected_delta={"changes": {}}, risk={"risk_class": "R2"},
                   validation=["ci"], rollback={"type": "git-revert"})
    assert "sha256:x" in body and "f1" in body


def test_catalog_complete():
    c = catalog()
    assert "shell.run" not in c
    assert all(v["executor"] for v in c.values())


def test_dry_run_observe_action():
    from platformforge.ops.executors.base import ObserveExecutor
    e = ObserveExecutor()
    r = e.run_step("s", "k8s.observe", {"resource_types": ["pods"]},
                   dry_run=True, transport=lambda *a: (0, "{}", ""))
    assert r.ok  # observe actions support dry_run


if __name__ == "__main__":
    pytest.main([__file__])
