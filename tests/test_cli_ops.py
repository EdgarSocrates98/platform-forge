"""Phase W — `platformforge ops` CLI surface: parser wiring, structured
output, refusal codes, dry-run default, host boundary."""

from __future__ import annotations

import json

import pytest

from platformforge.cli.main import main


def _plan(tmp_path):
    p = tmp_path / "plan.yaml"
    p.write_text("""
intent:
  intent_id: i1
  owner: team-a
  requested_by: bob
  reason: {type: drift, drift_ids: [d1]}
  target_resources: ["k8s:lab/apps/Deployment/web"]
  desired_change: {replicas: 3}
steps:
  - step_id: scale
    action: kubernetes.scale
    params: {kind: Deployment, name: web, namespace: apps,
             replicas: 3, current_replicas: 5}
expected_delta:
  changes: {resources: [{id: "dep/web", replicas: [5, 3]}]}
""")
    return str(p)


SPEC = """
intent:
  intent_id: cli-i1
  owner: team-a
  requested_by: bob
  reason: {type: drift, drift_ids: [d1]}
  target_resources: ["k8s:lab/apps/Deployment/web"]
  desired_change: {replicas: 3}
steps:
  - step_id: scale
    action: kubernetes.scale
    params: {kind: Deployment, name: web, namespace: apps,
             replicas: 3, current_replicas: 5}
expected_delta:
  changes: {resources: [{id: "dep/web", replicas: [5, 3]}]}
observation:
  captured_at: "2999-01-01T00:00:00Z"
  coverage: {complete: true}
approvals:
  - {approval_id: ap1, binds: envelope, actor: alice, role: owner}
environment: lab
transports: {kubernetes: {rc: 0, stdout: "deployment scaled"}}
verify:
  observations:
    immediate: {changes: {resources: [{id: "dep/web", replicas: [5, 3]}]}}
    stabilization: {changes: {resources: [{id: "dep/web", replicas: [5, 3]}]}}
    extended: {changes: {resources: [{id: "dep/web", replicas: [5, 3]}]}}
"""


class TestOpsSurface:
    def test_capabilities(self, capsys, tmp_path):
        code = main(["ops", "capabilities", "--repo", str(tmp_path)])
        out = json.loads(capsys.readouterr().out)
        assert code == 0
        assert out["platform_max_autonomy"] == "A4"
        kinds = set(out["actions"])
        assert "kubernetes.scale" in kinds
        assert "shell.run" not in kinds  # forbidden verbs never surface

    def test_runbook_list_and_show(self, capsys, tmp_path):
        assert main(["ops", "runbook", "list", "--repo", str(tmp_path)]) == 0
        out = json.loads(capsys.readouterr().out)
        ids = {r["id"] for r in out["runbooks"]}
        assert "replica-drift-restore" in ids
        assert main(["ops", "runbook", "replica-drift-restore", "--repo", str(tmp_path)]) == 0
        rb = json.loads(capsys.readouterr().out)
        assert rb["hash"].startswith("sha256:")

    def test_runbook_unknown_refusal(self, capsys, tmp_path):
        code = main(["ops", "runbook", "nope", "--repo", str(tmp_path)])
        out = json.loads(capsys.readouterr().out)
        assert code == 2
        assert out["refusal"] == "PF-OPS-RUNBOOK-UNKNOWN"
        assert "unlock" in out

    def test_delegate_refusal(self, capsys, tmp_path):
        code = main(["ops", "delegate", "--repo", str(tmp_path)])
        out = json.loads(capsys.readouterr().out)
        assert code == 2
        assert out["refusal"].startswith("PF-OPS")

    def test_plan_validate(self, capsys, tmp_path):
        code = main(["ops", "plan", "--plan", _plan(tmp_path), "--repo", str(tmp_path)])
        out = json.loads(capsys.readouterr().out)
        assert code == 0
        assert out["hash"].startswith("sha256:")

    def test_simulate_and_risk(self, capsys, tmp_path):
        assert main(["ops", "simulate", "--plan", _plan(tmp_path), "--repo", str(tmp_path)]) == 0
        sim = json.loads(capsys.readouterr().out)
        assert sim["schema"] == "platformforge/simulation-receipt/v1"
        assert (
            main(["ops", "risk", "--plan", _plan(tmp_path), "--environment", "lab", "--repo", str(tmp_path)])
            == 0
        )
        risk = json.loads(capsys.readouterr().out)
        assert risk["risk_class"].startswith("R")

    def test_policy_eval_deny_exit2(self, capsys, tmp_path):
        pols = tmp_path / "policies.yaml"
        pols.write_text("""
- policy_id: deny-lab
  when: {environment: lab}
  then: {decision: deny, reason: "lab deny-all"}
""")
        code = main(
            [
                "ops",
                "policy-eval",
                "--plan",
                _plan(tmp_path),
                "--policies",
                str(pols),
                "--environment",
                "lab",
                "--repo",
                str(tmp_path),
            ]
        )
        out = json.loads(capsys.readouterr().out)
        assert code == 2
        assert out["decision"] == "deny"


class TestOpsRun:
    def test_dry_run_converges_without_host(self, capsys, tmp_path):
        spec = tmp_path / "ops.yaml"
        spec.write_text(SPEC)
        code = main(["ops", "run", "--spec", str(spec), "--repo", str(tmp_path)])
        out = json.loads(capsys.readouterr().out)
        assert code == 0
        assert out["ok"] is True
        assert out["dry_run"] is True
        assert out["state"] == "converged"
        assert out["receipts"]["ledger_valid"] is True

    def test_forbidden_action_refused(self, capsys, tmp_path):
        spec = tmp_path / "bad.yaml"
        spec.write_text(SPEC.replace("kubernetes.scale", "shell.run"))
        code = main(["ops", "run", "--spec", str(spec), "--repo", str(tmp_path)])
        out = json.loads(capsys.readouterr().out)
        assert code == 2
        text = json.dumps(out)
        assert "PF-OPS-UNSTRUCTURED" in text or "PF-OPS" in text

    def test_persists_operation_store(self, capsys, tmp_path):
        spec = tmp_path / "ops.yaml"
        spec.write_text(SPEC)
        main(["ops", "run", "--spec", str(spec), "--repo", str(tmp_path)])
        capsys.readouterr()
        code = main(["ops", "store-list", "--repo", str(tmp_path)])
        out = json.loads(capsys.readouterr().out)
        assert code == 0
        assert out["audit_digest"].startswith("sha256:")
        code = main(["ops", "store-verify", "--operation-id", "cli-op", "--repo", str(tmp_path)])
        v = json.loads(capsys.readouterr().out)
        assert code == 0
        assert v["chain_valid"] is True

    def test_missing_spec_is_error_not_crash(self, tmp_path):
        with pytest.raises((FileNotFoundError, OSError)):
            main(["ops", "run", "--spec", str(tmp_path / "no.yaml"), "--repo", str(tmp_path)])
