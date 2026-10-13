"""Phase H — Router V2: §82 output shape, §83 modes, §88/§89 mandates,
§91 routing validation gate (no route may reference a missing agent)."""

from __future__ import annotations

from platformforge.agents.roster import resolve
from platformforge.routing import TaskSignal, load_routes, route, validate_routing

OUTPUT_KEYS = {"mode", "coordinator", "specialists", "reviewers",
               "verifier", "dag", "budget", "reasons", "fallbacks",
               "agents", "signal"}


def test_output_shape_and_deterministic_default():
    out = route(TaskSignal(task_type="lint"))
    assert OUTPUT_KEYS <= set(out)
    assert out["mode"] == "deterministic"
    assert out["agents"] == [] and out["dag"] == []
    assert out["budget"] == "tiny"


def test_single_specialist_mode():
    out = route(TaskSignal(task_type="analysis", domains=["k8s"]))
    assert out["mode"] == "single-specialist"
    assert out["specialists"] == ["platform-kubernetes-specialist"]
    assert out["verifier"] == "platform-verifier"
    assert "platform-evidence-reviewer" in out["reviewers"]
    assert out["dag"][-1]["agent"] == "platform-verifier"


def test_multi_specialist_mode():
    out = route(TaskSignal(task_type="analysis",
                           domains=["k8s", "security"]))
    assert out["mode"] == "multi-specialist"
    assert {"platform-kubernetes-specialist",
            "platform-security-specialist"} <= set(out["specialists"])


def test_coordinated_cross_domain():
    out = route(TaskSignal(task_type="analysis",
                           domains=["k8s", "iac", "security"]))
    assert out["mode"] == "coordinated"
    assert out["coordinator"] == "platform-orchestrator"
    assert out["budget"] == "deep"


def test_incident_coordination():
    out = route(TaskSignal(task_type="incident", domains=["k8s"]))
    assert out["mode"] == "coordinated"
    assert out["coordinator"] == "platform-incident-coordinator"
    out2 = route(TaskSignal(task_type="analysis",
                            incident_status="active"))
    assert out2["coordinator"] == "platform-incident-coordinator"


def test_fleet_scope_routes_to_fleet_coordinator():
    out = route(TaskSignal(task_type="analysis", domains=["fleet"],
                           fleet_scope=True))
    assert out["mode"] == "coordinated"
    assert out["coordinator"] == "platform-fleet-coordinator"


def test_critical_review_mandatory_production_mutation():
    out = route(TaskSignal(task_type="change", production=True,
                           mutability="mutate"))
    assert out["mode"] == "critical-review"
    assert "platform-operations-safety-reviewer" in out["reviewers"]
    assert "platform-security-reviewer" in out["reviewers"]
    assert any(s.get("external") for s in out["dag"])  # human gate
    assert out["coordinator"] == "platform-change-coordinator"


def test_critical_review_destructive_and_fleet_opt():
    assert route(TaskSignal(task_type="change",
                            destructive=True))["mode"] \
        == "critical-review"
    assert route(TaskSignal(task_type="analysis", optimization=True,
                            fleet_scope=True))["mode"] \
        == "critical-review"


def test_debate_only_on_triggers():
    assert route(TaskSignal(task_type="analysis", domains=["k8s"],
                            conflict=True))["mode"] == "debate"
    assert "platform-debate-referee" in route(
        TaskSignal(task_type="analysis", domains=["k8s"],
                   conflict=True))["reviewers"]
    assert route(TaskSignal(task_type="analysis", domains=["k8s"],
                            comparison=True))["mode"] == "debate"
    assert route(TaskSignal(task_type="analysis", domains=["k8s"],
                            risk="high",
                            evidence_completeness=0.3))["mode"] \
        == "debate"
    # high risk WITH evidence does not open a debate
    out = route(TaskSignal(task_type="analysis", domains=["k8s"],
                           risk="high", evidence_completeness=0.9))
    assert out["mode"] != "debate"


def test_no_debate_for_low_risk_default():
    out = route(TaskSignal(task_type="analysis", domains=["iac"]))
    assert out["mode"] == "single-specialist"
    assert out["budget"] == "small"


def test_routing_validation_gate_clean():
    out = validate_routing()
    assert out["ok"], out["problems"]
    assert out["routes"] > 0 and out["agents"] == 41


def test_routing_validation_catches_missing(tmp_path):
    import yaml
    bad = tmp_path / "routing.yaml"
    bad.write_text(yaml.safe_dump({"routes": [
        {"name": "ghost", "when": {"task_type": "analysis"},
         "agents": ["platform-ghost-agent"]}]}))
    out = validate_routing(bad)
    assert not out["ok"]
    assert any("platform-ghost-agent" in p for p in out["problems"])


def test_every_table_ref_resolves():
    for r in load_routes():
        for key in ("agents", "add_specialists", "add_reviewers",
                    "coordinator"):
            ref = r.get(key)
            for a in ([ref] if isinstance(ref, str) else (ref or [])):
                assert resolve(a) is not None, (r["name"], a)
