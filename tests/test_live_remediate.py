"""Phase K — remediation planning: source-of-truth, simulation,
planned graph, approval envelope. Never applies."""

from __future__ import annotations

import json

from platformforge.live.remediate import (
    AUTO_APPLY_REFUSAL,
    approval_envelope,
    plan_remediation,
    remediate,
    simulate_plan,
)

DRIFT = [
    {"drift_class": "config-drift", "resource": "deploy/api",
     "fact_ids": ["f1"], "diff": {"replicas": {"desired": 3,
                                               "observed": 2}}},
    {"drift_class": "security-drift", "resource": "s3/app",
     "fact_ids": ["f2"]},
    {"drift_class": "observed-out-of-band", "resource": "pod/rogue",
     "fact_ids": ["f3"]},
    {"drift_class": "stale-observation", "resource": "svc/old",
     "fact_ids": []},
    {"drift_class": "converged", "resource": "svc/ok"},
]


class TestPlan:

    def test_actions_cite_evidence(self):
        plan = plan_remediation(DRIFT)
        by_res = {a["resource"]: a for a in plan["actions"]}
        assert by_res["deploy/api"]["verb"] == "apply-desired"
        assert by_res["deploy/api"]["mutating"] is True
        assert by_res["deploy/api"]["evidence"] == ["f1"]
        assert by_res["pod/rogue"]["verb"] == "decide:adopt|remove"
        assert by_res["pod/rogue"]["mutating"] is False
        assert by_res["svc/old"]["verb"] == "re-observe"

    def test_converged_skipped(self):
        plan = plan_remediation(DRIFT)
        assert "svc/ok" not in {a["resource"] for a in plan["actions"]}

    def test_high_risk_first(self):
        plan = plan_remediation(DRIFT)
        assert plan["actions"][0]["resource"] == "s3/app"
        assert plan["counts"]["mutating"] == 2
        assert plan["counts"]["decision_required"] == 1


class TestSimulate:

    def test_resolves_only_mutating(self):
        plan = plan_remediation(DRIFT)
        sim = simulate_plan(plan, DRIFT)["simulation"]
        assert "deploy/api|config-drift" in sim["resolved"]
        assert "s3/app|security-drift" in sim["resolved"]
        pending_keys = {e["resource"] for e in sim["pending"]}
        assert "pod/rogue" in pending_keys      # decision pending
        assert "svc/old" in pending_keys        # re-observe pending
        assert "svc/ok" in pending_keys         # converged untouched

    def test_empty_drift_full_confidence(self):
        plan = plan_remediation([])
        sim = simulate_plan(plan, [])["simulation"]
        assert sim["confidence"] == "full" and sim["pending_count"] == 0


class TestEnvelope:

    def test_envelope_is_awaiting_and_never_applies(self):
        out = remediate(DRIFT)
        env = out["envelope"]
        assert env["status"] == "awaiting-approval"
        assert env["auto_apply"] is False
        assert env["apply_refusal"] == AUTO_APPLY_REFUSAL
        assert env["plan_id"] == f"plan-{env['plan_hash']}"

    def test_hash_binds_plan_content(self):
        e1 = approval_envelope(plan_remediation(DRIFT),
                               simulate_plan(plan_remediation(DRIFT),
                                             DRIFT))["envelope"]
        modified = plan_remediation(DRIFT + [
            {"drift_class": "config-drift", "resource": "x"}])
        e2 = approval_envelope(modified,
                               simulate_plan(modified, DRIFT))["envelope"]
        assert e1["plan_hash"] != e2["plan_hash"]

    def test_json_deterministic(self):
        a = json.dumps(remediate(DRIFT)["envelope"]["plan_hash"])
        b = json.dumps(remediate(DRIFT)["envelope"]["plan_hash"])
        assert a == b


class TestCli:

    def test_live_plan_verb(self, tmp_path, capsys):
        from platformforge.cli.main import main
        f = tmp_path / "drift.json"
        f.write_text(json.dumps(DRIFT))
        code = main(["live", "plan", "--repo", str(tmp_path),
                     "--drift-events", str(f)])
        out = json.loads(capsys.readouterr().out)
        assert code == 0
        assert out["envelope"]["status"] == "awaiting-approval"
        assert out["envelope"]["auto_apply"] is False
        assert out["counts"]["mutating"] == 2

    def test_live_plan_strict_fails_on_mutating(self, tmp_path, capsys):
        from platformforge.cli.main import main
        f = tmp_path / "drift.json"
        f.write_text(json.dumps(DRIFT))
        code = main(["live", "plan", "--repo", str(tmp_path),
                     "--drift-events", str(f), "--strict"])
        capsys.readouterr()
        assert code == 2

    def test_live_plan_refuses_without_input(self, tmp_path, capsys):
        from platformforge.cli.main import main
        code = main(["live", "plan", "--repo", str(tmp_path)])
        out = json.loads(capsys.readouterr().out)
        assert code == 2
        assert out["refusal"] == "PF-LIVE-NO-DRIFT-INPUT"
