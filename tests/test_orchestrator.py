"""Phase C — orchestration machinery: taskspec lifecycle, planner,
DAG build/validation, verifier independence, critic, guardian, referee."""

from __future__ import annotations

from platformforge.agents import (
    AGENTS,
    AgentRefusal,
    adversarial_review,
    build_dag,
    checkpoint,
    load_loops,
    plan,
    prepare,
    referee,
    release_review,
    require_sealed,
    resume,
    review,
    seal,
    validate_dag,
    verify_run,
)
from platformforge.agents.orchestrator import DagNode
from platformforge.agents.verifier import PRODUCER_ROLES


def sealed_spec(**kw):
    spec = plan(kw.pop("intent", "analyze my kubernetes manifests"),
                **kw)
    return seal(review(spec))


# --- taskspec lifecycle -------------------------------------------------


def test_draft_review_seal_flow():
    spec = plan("check terraform state", domains=("iac",))
    assert spec.state == "draft"
    reviewed = review(spec)
    assert reviewed.state == "reviewed"
    sealed = seal(reviewed)
    assert sealed.state == "sealed" and sealed.spec_hash
    # sealed specs are immutable docs — a fresh hash after transition
    assert sealed.spec_hash != spec.spec_hash


def test_review_rejects_high_risk_without_rollback():
    spec = plan("apply the upgrade", risk="high",
                rollback_requirement="none",
                acceptance_criteria=("x",), complexity="medium")
    out = review(spec)
    assert out.state == "rejected"
    assert any("rollback" in n for n in out.review_notes)


def test_seal_refuses_draft_and_rejected():
    draft = plan("x", domains=("iac",))
    out = seal(draft)
    assert out["refusal"] == AgentRefusal.SPEC_UNSEALED
    rejected = review(plan("apply x", risk="high",
                           complexity="medium"))
    out2 = seal(rejected)
    assert out2["refusal"] == AgentRefusal.SPEC_REJECTED


def test_require_sealed_blocks_unsealed_complex():
    spec = plan("audit entire platform", domains=("iac", "k8s", "aws"))
    assert spec.complexity == "high"
    assert require_sealed(spec, complex_=True)["refusal"] \
        == AgentRefusal.SPEC_UNSEALED


def test_planner_infers_domains_and_forbids_mutations():
    spec = plan("check terraform and kubernetes drift")
    assert {"iac", "k8s"} <= set(spec.domains)
    assert "ops.apply" in spec.forbidden_capabilities
    assert spec.autonomy == "read-only"


# --- DAG -----------------------------------------------------------------

LOOP = {"coordinator": "platform-orchestrator", "stages": [
    {"id": "extract", "agent": "platform-graph-specialist"},
    {"id": "work", "fanout": "domains", "after": ["extract"]},
    {"id": "verify", "agent": "platform-verifier", "after": ["work"]}]}


def test_build_dag_fanout_waits_for_all():
    nodes, missing = build_dag(
        LOOP, plan("x", domains=("iac",)),
        specialists=["platform-iac-specialist",
                     "platform-kubernetes-specialist"])
    assert not missing
    work = [n for n in nodes if n.stage.startswith("work:")]
    assert len(work) == 2
    verify = next(n for n in nodes if n.stage == "verify")
    assert set(verify.depends_on) == {w.stage for w in work}


def test_validate_dag_verifier_terminal():
    nodes, _ = build_dag(LOOP, plan("x"), specialists=["platform-iac-specialist"])
    assert validate_dag(nodes) == []
    bad = nodes + [DagNode(stage="late", agent="platform-iac-specialist",
                           depends_on=("verify",))]
    assert any("verifier" in e for e in validate_dag(bad))


def test_prepare_full_loop_resolves_and_bounds_fanout():
    spec = sealed_spec(domains=("iac", "k8s"))
    plan_out = prepare(spec, loop_name="x",
                       loops={"x": LOOP},
                       specialists=["platform-iac-specialist",
                                    "platform-kubernetes-specialist"])
    assert plan_out.refusal_doc is None
    assert plan_out.envelope.agents_used == 4
    stages = plan_out.topological_stages()
    assert stages[0][0].stage == "extract"
    assert stages[-1][0].stage == "verify"


def test_prepare_refuses_missing_agents():
    spec = sealed_spec(domains=("iac",))
    loop = {"stages": [{"id": "s", "agent": "platform-ghost"}]}
    out = prepare(spec, loop_name="l", loops={"l": loop})
    assert out.refusal_doc["refusal"] \
        == AgentRefusal.ROUTE_UNRESOLVED
    assert "platform-ghost" in out.refusal_doc["why"]


def test_prepare_refuses_unknown_loop_and_unsealed():
    spec = sealed_spec(domains=("iac",))
    out = prepare(spec, loop_name="nope", loops={"a": {"stages": []}})
    assert out.refusal_doc["refusal"] \
        == AgentRefusal.ROUTE_UNRESOLVED
    draft = plan("audit the entire fleet", domains=("k8s",))
    out2 = prepare(draft, loop_name="x", loops={"x": LOOP})
    assert out2.refusal_doc["refusal"] \
        == AgentRefusal.SPEC_UNSEALED


def test_catalog_loops_load():
    loops = load_loops()
    assert {"platform-audit", "incident", "change", "fleet",
            "optimization", "single"} <= set(loops)


def test_checkpoint_resume_preserves_spec_binding():
    spec = sealed_spec(domains=("iac",))
    p = prepare(spec, loop_name="x", loops={"x": LOOP},
                specialists=["platform-iac-specialist"])
    cp = checkpoint(p.run, ("extract",))
    out = resume(p.run, cp, spec)
    assert out.verdict == "candidate"
    other = sealed_spec(intent="different question", domains=("k8s",))
    bad = resume(p.run, cp, other)
    assert bad["refusal"] == AgentRefusal.SPEC_UNSEALED


# --- verifier ------------------------------------------------------------


def test_verify_run_confirmed_with_evidence():
    spec = sealed_spec(domains=("iac",))
    p = prepare(spec, loop_name="x", loops={"x": LOOP},
                specialists=["platform-iac-specialist"])
    p.run.evidence = ("F-1", "F-2")
    p.run.verifier = "platform-verifier"
    out = verify_run(p.run, spec=spec,
                     evidence_index={"F-1": {}, "F-2": {}})
    assert out["verdict"] == "confirmed"
    assert out["receipt"]["evidence_count"] == 2


def test_verify_run_independence_refusal():
    spec = sealed_spec(domains=("iac",))
    p = prepare(spec, loop_name="x", loops={"x": LOOP},
                specialists=["platform-iac-specialist"])
    p.run.evidence = ("F-1",)
    out = verify_run(p.run, spec=spec,
                     producers=("platform-verifier",),
                     verifier="platform-verifier")
    assert out["refusal"] == AgentRefusal.SELF_VERIFICATION


def test_verify_run_no_evidence_unresolved():
    spec = sealed_spec(domains=("iac",))
    p = prepare(spec, loop_name="x", loops={"x": LOOP},
                specialists=["platform-iac-specialist"])
    out = verify_run(p.run, spec=spec)
    assert out["verdict"] == "unresolved"
    assert out["refusal"] == AgentRefusal.NO_EVIDENCE


def test_verify_run_never_upgrades_refuted():
    spec = sealed_spec(domains=("iac",))
    p = prepare(spec, loop_name="x", loops={"x": LOOP},
                specialists=["platform-iac-specialist"])
    p.run.evidence = ("F-1",)
    p.run.verdict = "refuted"
    out = verify_run(p.run, spec=spec,
                     evidence_index={"F-1": {}})
    assert out["verdict"] == "refuted"


# --- critic / guardian ----------------------------------------------------


def test_critic_flags_missing_requirements():
    from dataclasses import replace
    weak = replace(plan("look around", domains=("iac",)),
                   evidence_requirements=(), acceptance_criteria=())
    sealed = seal(review(plan("look", domains=("iac",),
                              acceptance_criteria=("x",))))
    p = prepare(sealed, loop_name="x", loops={"x": LOOP},
                specialists=["platform-iac-specialist"])
    out = adversarial_review(p, weak)
    assert out["verdict"] == "risk"
    axes = {a["axis"] for a in out["attacks"]}
    assert axes == {"assumption", "missing-evidence", "fail-open",
                    "partial-coverage", "rollback", "source-ownership",
                    "regression"}


def test_guardian_ready_and_blockers():
    ok = release_review(
        {"tests": {"pass": 10, "fail": 0},
         "evals": {"pass": 5, "fail": 0},
         "lab": {"pass": 3, "fail": 0},
         "docs_drift": True, "package": True, "gates": {"lint": True}})
    assert ok["verdict"] == "READY"
    bad = release_review({"tests": {"pass": 1, "fail": 1}})
    assert bad["verdict"] == "BLOCKED"
    assert any("missing signal" in b for b in bad["blockers"])
    assert any("tests" in b for b in bad["blockers"])


# --- referee -------------------------------------------------------------


def test_referee_evidence_beats_prose():
    out = referee([
        {"agent": "a", "claim": "fancy confident prose",
         "evidence_tier": 6, "freshness": "stale"},
        {"agent": "b", "claim": "measured",
         "evidence_fact_ids": ("F-1",), "evidence_tier": 1,
         "freshness": "current", "coverage": 0.9}])
    assert out["winner"]["agent"] == "b"
    assert not out["unresolved"]
    assert len(out["axes"]) == 10


def test_referee_no_evidence_unresolved():
    out = referee([{"agent": "a", "claim": "trust me",
                    "evidence_tier": 7}])
    assert out["unresolved"]
    assert out["receipt"]["refusal_code"] == "platform.evidence.unresolved"


def test_referee_tie_is_explicit():
    pos = {"evidence_fact_ids": ("F-1",), "evidence_tier": 2,
           "freshness": "current", "coverage": 0.5}
    out = referee([dict(pos, agent="x", claim="c1"),
                   dict(pos, agent="y", claim="c2")])
    assert out["tied"]


# --- roster sanity ----------------------------------------------------------


def test_roster_has_orchestration_roles():
    roles = {a.name: a.role for a in AGENTS.values()}
    for name, role in (("platform-planner", "planner"),
                       ("platform-task-spec-reviewer", "reviewer"),
                       ("platform-adversarial-critic", "critic"),
                       ("platform-verifier", "verifier"),
                       ("platform-release-guardian", "guardian")):
        assert roles.get(name) == role, name
    assert "verifier" not in PRODUCER_ROLES
