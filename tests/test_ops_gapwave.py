"""X-wave gap-closure tests: approval bounds enforcement, required_type
escalation, offline transport refusal, rollback execution, new verbs."""

from __future__ import annotations

import json

from platformforge.cli.main import main
from platformforge.ops import engine
from platformforge.ops.approval import Approval
from platformforge.ops.models import ChangeIntent, ExpectedDelta, PlanStep, Reason
from platformforge.ops.operation import LockTable, Operation, OperationLedger
from platformforge.ops.policy import PolicyDecision


def _stack(params=None, env_ctx=None):
    intent = ChangeIntent(
        intent_id="i1", owner="team", requested_by="bob",
        reason=Reason(type="drift", drift_ids=["d1"]),
        target_resources=["k8s:lab/apps/Deployment/web"],
        desired_change={"replicas": 3})
    plan = engine.plan(intent, steps=[PlanStep(
        step_id="scale", action="kubernetes.scale",
        params=params or {"kind": "Deployment", "name": "web",
                          "namespace": "apps", "replicas": 3,
                          "current_replicas": 5})],
        expected_delta=ExpectedDelta())
    risk = engine.assess_risk(plan, env_ctx or {"environment": "lab"})
    decisions = [PolicyDecision(policy_id="p", decision="allow")]
    env = engine.mint_envelope(plan, execution_id="e1",
                               decisions=decisions, approvals=[],
                               risk=risk, rollback=None)
    assert not isinstance(env, dict), env
    env.freeze()
    return intent, plan, env


def _run(env, approvals, **kw):
    op = Operation(operation_id="op1", intent_id=env.intent_id,
                   resources=list(env.scope))
    kw.setdefault("preconditions", {
        "observation": {"captured_at": "2999-01-01T00:00:00Z",
                        "coverage": {"complete": True}},
        "environment": "lab"})
    return engine.execute(
        op, env, approvals=approvals, ledger=OperationLedger(),
        locks=LockTable(),
        transports={"kubernetes": lambda *a, **k: (0, "ok", "")},
        **kw)


class TestApprovalBoundsEnforced:
    def test_bounds_within_passes(self):
        _, _, env = _stack()
        ap = Approval(approval_id="a", subject_hash=env.hash(),
                      scope=list(env.scope), actor="alice",
                      parameter_bounds={"replicas": [1, 5]})
        out = _run(env, [ap])
        assert out["ok"] is True, out

    def test_bounds_exceeded_refuses(self):
        _, _, env = _stack(params={
            "kind": "Deployment", "name": "web", "namespace": "apps",
            "replicas": 50, "current_replicas": 5})
        ap = Approval(approval_id="a", subject_hash=env.hash(),
                      scope=list(env.scope), actor="alice",
                      parameter_bounds={"replicas": [1, 5]})
        out = _run(env, [ap])
        assert out["ok"] is False
        assert out["refusal"]["refusal"] == "PF-OPS-APPROVAL-BOUNDS"


class TestRequiredType:
    def test_require_dual_human_decision(self):
        _, plan, _ = _stack()
        risk = engine.assess_risk(plan, {"environment": "lab"})
        env = engine.mint_envelope(
            plan, execution_id="e1",
            decisions=[PolicyDecision(policy_id="p",
                                      decision="require-dual-human")],
            approvals=[], risk=risk, rollback=None)
        ap = Approval(approval_id="a", subject_hash=env.hash(),
                      scope=list(env.scope), actor="alice",
                      type="single-human")
        out = _run(env, [ap])
        assert out["ok"] is False
        assert out["stage"] == "approval"


class TestRollbackExecution:
    def test_execute_rollback_reaches_rolled_back(self):
        _, _, env = _stack()
        op = Operation(operation_id="op1", intent_id="i1",
                       resources=list(env.scope))
        ledger = OperationLedger()
        ap = Approval(approval_id="a", subject_hash=env.hash(),
                      scope=list(env.scope), actor="alice")
        out = engine.execute(
            op, env, approvals=[ap], ledger=ledger, locks=LockTable(),
            transports={"kubernetes": lambda *a, **k: (0, "ok", "")},
            preconditions={
                "observation": {"captured_at": "2999-01-01T00:00:00Z",
                                "coverage": {"complete": True}},
                "environment": "lab"})
        assert out["ok"]
        engine.finalize_verify(op, ledger, {"convergence": "regressed"})
        assert op.state == "rollback-planned"
        rb = engine.execute_rollback(
            op, env, transports={
                "kubernetes": lambda *a, **k: (0, "rolled back", "")},
            ledger=ledger)
        assert rb["ok"] is True
        assert op.state == "rolled-back"
        assert ledger.verify_chain()
        events = [e.event for e in ledger.entries]
        assert "rollback.started" in events
        assert "rollback.completed" in events

    def test_rollback_refuses_from_terminal_state(self):
        _, _, env = _stack()
        op = Operation(operation_id="op2", state="converged")
        out = engine.execute_rollback(op, env)
        assert out["ok"] is False


class TestCliOfflineAndVerbs:
    def test_live_snapshot_offline_refuses(self, capsys, tmp_path):
        code = main(["live", "snapshot", "--offline",
                     "--repo", str(tmp_path)])
        out = json.loads(capsys.readouterr().out)
        assert code == 2
        assert out["refusal"] == "PF-LIVE-OFFLINE"

    def test_ops_execute_offline_refuses(self, capsys, tmp_path):
        spec = tmp_path / "s.yaml"
        spec.write_text("intent: {intent_id: x}\nsteps: []\n")
        code = main(["ops", "run", "--spec", str(spec), "--execute",
                     "--offline", "--repo", str(tmp_path)])
        out = json.loads(capsys.readouterr().out)
        assert code == 2
        assert out["refusal"] == "PF-OPS-OFFLINE"

    def test_ops_approve_mints_signed_artifact(self, capsys, tmp_path):
        code = main(["ops", "approve", "--subject-hash", "sha256:abc",
                     "--actor", "alice", "--repo", str(tmp_path)])
        out = json.loads(capsys.readouterr().out)
        assert code == 0
        assert out["signature"].startswith("sha256:")
        assert out["subject_hash"] == "sha256:abc"

    def test_ops_status_and_history(self, capsys, tmp_path):
        spec = tmp_path / "ops.yaml"
        spec.write_text(_SPEC)
        main(["ops", "run", "--spec", str(spec), "--repo", str(tmp_path)])
        capsys.readouterr()
        assert main(["ops", "status", "--operation-id", "cli-op",
                     "--repo", str(tmp_path)]) == 0
        st = json.loads(capsys.readouterr().out)
        assert st["state"] in ("verifying", "converged")
        assert st["ledger"]["chain_valid"] is True
        assert main(["ops", "history", "--repo", str(tmp_path)]) == 0
        h = json.loads(capsys.readouterr().out)
        assert h["count"] > 0

    def test_ops_analytics(self, capsys, tmp_path):
        spec = tmp_path / "ops.yaml"
        spec.write_text(_SPEC)
        main(["ops", "run", "--spec", str(spec), "--repo", str(tmp_path)])
        capsys.readouterr()
        code = main(["ops", "analytics", "--repo", str(tmp_path)])
        out = json.loads(capsys.readouterr().out)
        assert code == 0
        assert out["operations"]["total"] >= 1
        assert "success_rate" in out["operations"]


_SPEC = """
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
transports: {kubernetes: {rc: 0, stdout: "scaled"}}
"""


class TestReconcilePerTypeCoverage:
    """X1c: per-type coverage gates absence; identity joins layers."""

    def _env(self, coverage):
        from platformforge.live.models import ObservationEnvelope
        return ObservationEnvelope.new(
            collector="kubernetes", version="t", provider="kubernetes",
            source_type="observed",
            captured_at="2999-01-01T00:00:00Z",
            fresh_until="3999-01-01T00:00:00Z",
            scope={"resource_types": ["k8s:apps/Deployment",
                                      "k8s:core/ConfigMap"]},
            coverage=coverage,
            objects=[])

    def test_permission_limited_type_is_unresolved_not_missing(self):
        from platformforge.live.reconcile import norm_facts, norm_observed, reconcile
        desired = norm_facts([
            {"fact_id": "f1", "kind": "k8s:apps/Deployment",
             "location": "k8s://lab/prod/Deployment/api",
             "attrs": {"namespace": "prod", "name": "api"}}], "desired")
        env = self._env({"status": "partial", "per_resource_type": {
            "k8s:apps/Deployment": "permission-limited",
            "k8s:core/ConfigMap": "complete"}})
        out = reconcile(desired=desired, observed=norm_observed(env))
        assert out["drift"] == []
        assert out["unresolved"][0]["drift_class"] == "permission-unknown"
        assert "permission-limited" in out["unresolved"][0]["reason"]

    def test_complete_type_concludes_missing(self):
        from platformforge.live.reconcile import norm_facts, norm_observed, reconcile
        desired = norm_facts([
            {"fact_id": "f1", "kind": "k8s:core/ConfigMap",
             "location": "k8s://lab/prod/ConfigMap/cfg",
             "attrs": {"namespace": "prod", "name": "cfg"}}], "desired")
        env = self._env({"status": "partial", "per_resource_type": {
            "k8s:apps/Deployment": "permission-limited",
            "k8s:core/ConfigMap": "complete"}})
        out = reconcile(desired=desired, observed=norm_observed(env))
        classes = {e["drift_class"] for e in out["drift"]}
        assert "desired-missing-observed" in classes
        assert out["unresolved"] == []

    def test_uid_suffixed_resource_id_matches_base(self):
        from platformforge.live.models import ObservationEnvelope
        from platformforge.live.reconcile import norm_facts, norm_observed, reconcile
        desired = norm_facts([
            {"fact_id": "f1", "kind": "k8s:apps/Deployment",
             "location": "k8s://lab/prod/Deployment/api",
             "attrs": {"namespace": "prod", "name": "api",
                       "spec.replicas": 2}}], "desired")
        env = ObservationEnvelope.new(
            collector="kubernetes", version="t", provider="kubernetes",
            source_type="observed",
            captured_at="2999-01-01T00:00:00Z",
            fresh_until="3999-01-01T00:00:00Z",
            scope={"resource_types": ["k8s:apps/Deployment"]},
            coverage={"status": "complete"},
            objects=[{"resource_id": "k8s://lab/prod/Deployment/api#u1",
                      "resource_type": "k8s:apps/Deployment",
                      "namespace": "prod", "name": "api", "uid": "u1",
                      "attributes": {"spec.replicas": 2}}])
        out = reconcile(desired=desired, observed=norm_observed(env))
        classes = {e["drift_class"] for e in out["drift"]}
        assert "converged" in classes
        assert "desired-missing-observed" not in classes
        assert "observed-orphan" not in classes

    def test_identities_block_present(self):
        from platformforge.live.reconcile import norm_facts, norm_observed, reconcile
        env = self._env({"status": "complete"})
        out = reconcile(desired=norm_facts([], "desired"),
                        observed=norm_observed(env))
        assert "identities" in out
