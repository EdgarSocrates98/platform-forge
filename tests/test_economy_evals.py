"""Phase R — economy evals (§216+): named evaluations, property
invariants, adversarial cases E1–E12.

Each named eval from the spec is an executable scenario against the real
economy modules — graded where the machinery lives (module level), same
ethos as the corpus runner.
"""

from __future__ import annotations

import time

import pytest

from platformforge.agents.debate import run_debate
from platformforge.agents.uniqueness import AgentContribution, AgentUniqueness
from platformforge.context.capsule import ContextCapsule
from platformforge.context.gateway import ContextGateway, ContextRequest
from platformforge.economy.budget import BudgetEnvelope, Limit
from platformforge.economy.cache import CacheStore
from platformforge.economy.checkpoint import CheckpointStore, EconomyCheckpoint
from platformforge.economy.collection import (
    evidence_gate,
    fleet_delta,
)
from platformforge.economy.pricing import cost
from platformforge.economy.reconcile import reconcile
from platformforge.economy.verifyplan import VerificationPlanner
from platformforge.routing.decision import RoutingRequest, promote_verdict
from platformforge.routing.router import TaskSignal, route
from platformforge.tokensave.ledger import LedgerEntry, TokenLedger

# --- named evaluations -----------------------------------------------------

def test_eval_cache_rule_change_facts_hit_findings_miss(tmp_path):
    """cache: rule catalog change → facts reusable, findings miss."""
    s = CacheStore(tmp_path / "c")
    s.put("fact", "f1", {"v": 1},
          {"artifact_hash": "a", "extractor_version": "e1"})
    s.put("finding", "fd1", {"r": "x"},
          {"artifact_hash": "a", "rule_catalog_hash": "rules-v1"})
    deps = {"artifact_hash": "a", "extractor_version": "e1",
            "rule_catalog_hash": "rules-v2"}
    assert s.get("fact", "f1", deps)[0].state == "hit"
    assert s.get("finding", "fd1", deps)[0].state != "hit"


def test_eval_knowledge_change_recommendations_invalidated(tmp_path):
    """cache: knowledge change → facts hit, analysis/recommendations miss."""
    s = CacheStore(tmp_path / "c")
    s.put("fact", "f1", 1, {"artifact_hash": "a"})
    s.put("analysis", "rec1", {"rec": "r"},
          {"rule_catalog_hash": "rv", "knowledge_hash": "k1"})
    deps = {"artifact_hash": "a", "rule_catalog_hash": "rv",
            "knowledge_hash": "k2"}
    assert s.get("fact", "f1", deps)[0].state == "hit"
    assert s.get("analysis", "rec1", deps)[0].state != "hit"


def test_eval_context_budget_essential_refuses(tmp_path):
    """context budget: essential evidence cannot fit → named refusal."""
    gw = ContextGateway(tmp_path / "g")
    res = gw.build(ContextRequest(
        task="t", essential_bytes=10_000, budget_bytes=100,
        facts=[{"fact_id": "f1"}]))
    assert res["refusal"] == "PF-CONTEXT-ESSENTIAL"
    assert res["sufficiency"]["state"] == "insufficient"


def test_eval_resume_counts_previous_spend(tmp_path):
    """resume: previous spend remains counted — never resets."""
    st = CheckpointStore(tmp_path / "ck")
    st.save(EconomyCheckpoint(
        run_id="r1", spent_budget={"tokens": 500, "agents": 2}))
    res = st.resume("r1", current_deps={})
    assert res["resumed"] is True
    assert res["spent_budget"]["tokens"] == 500
    assert res["spent_budget"]["agents"] == 2


def test_eval_reconcile_mismatch_visible():
    """reconcile: planned vs observed mismatch is visible, not hidden."""
    rec = reconcile(planned={"tokens": 1000}, observed={"tokens": 2400})
    ax = rec.axes["tokens"]
    assert ax.state == "over" and ax.error_pct == pytest.approx(140.0)


def test_eval_missing_pricing_no_dollar_claim():
    """pricing: missing rate → unresolved + refusal, never a dollar."""
    r = cost([], "aws", "some-model", 1000, 100)
    assert r["state"] == "unresolved"
    assert r["refusal"] == "PF-ECONOMY-PRICING-MISSING"


def test_eval_selective_verification_security_preserved():
    """verification: security changes always include security checks."""
    plan = VerificationPlanner().plan(risk="high", touches_security=True)
    assert "security-verification" in plan.checks
    assert plan.floor != "V0-static"     # high risk cannot stop at V0


def test_eval_simple_task_no_multiagent():
    """routing: a simple task must not route to multi-agent."""
    d = route(TaskSignal(task_type="lint", complexity="low", risk="low",
                         domains=[], blast_radius="local"))
    assert d["mode"] in ("deterministic", "single-specialist")
    assert len(d.get("specialists", [])) <= 1


def test_eval_agent_duplication_detected():
    """agentic: uniqueness audit flags duplicated contribution."""
    u = AgentUniqueness(run_id="r").audit([
        AgentContribution(agent="sre-1", contribution_ids=["e1", "e2"]),
        AgentContribution(agent="sre-2", contribution_ids=["e1", "e3"]),
    ])
    assert u.duplicated_contribution.get("sre-2") == ["e1"]
    assert u.unique_contribution["sre-1"] == ["e1", "e2"]


def test_eval_debate_stagnation_stops():
    """debate: a round with no new evidence stops the debate."""
    res = run_debate("adopt X?", positions=[
        {"agent": "a", "claim": "yes", "evidence": ["e1"], "round": 0},
        {"agent": "b", "claim": "no", "evidence": ["e2"], "round": 0},
        {"agent": "a", "claim": "still yes", "evidence": ["e1"],
         "round": 1},                       # round 1 adds nothing new
    ], max_rounds=5)
    assert res["debate"]["stopped_early"] is True
    assert res["debate"]["stagnant_round"] == 1


def test_eval_fleet_context_bounded(tmp_path):
    """fleet: a capsule is bounded bytes — the fleet never expands inline."""
    gw = ContextGateway(tmp_path / "g")
    res = gw.build(ContextRequest(
        task="fleet audit", scope="fleet",
        facts=[{"fact_id": "f1", "value": "v"}],
        graph_refs=["graph://fleet/summary"], budget_bytes=2000))
    assert res["bytes"] <= 2000 or res.get("refusal")
    # refs, not payload: the capsule carries graph refs, not members
    assert "members" not in res["capsule"]


def test_eval_stale_observation_not_fresh(tmp_path):
    """stale cache: TTL expiry invalidates the observation."""
    s = CacheStore(tmp_path / "c")
    s.put("analysis", "obs1", {"cpu": 1}, {}, ttl_s=0)
    time.sleep(0.01)
    dec, _ = s.get("analysis", "obs1", {})
    assert dec.state != "hit"


def test_eval_partial_token_observability_separate(tmp_path):
    """ledger: observed and estimated never silently combine."""
    led = TokenLedger(tmp_path)
    led.record(LedgerEntry(operation="m1", input_tokens=100,
                          token_basis="observed", transcript_ref="t1"))
    led.record(LedgerEntry(operation="m2", input_tokens_est=50,
                          token_basis="estimated"))
    rep = led.report()
    assert rep["input_tokens_observed"] == 100
    assert rep["input_tokens_estimated"] == 50
    assert rep["basis_counts"]["observed"] == 1
    assert rep["basis_counts"]["estimated"] == 1


# --- property invariants ------------------------------------------------------

def test_property_resume_never_resets_or_downgrades(tmp_path):
    st = CheckpointStore(tmp_path / "ck")
    st.save(EconomyCheckpoint(run_id="r", routing_profile="deep",
                            spent_budget={"tokens": 999}))
    res = st.resume("r", current_deps={}, requested_profile="economy")
    assert res["refusal"] == "PF-CHECKPOINT-DOWNGRADE"
    ok = st.resume("r", current_deps={}, requested_profile="strict")
    assert ok["resumed"] and ok["spent_budget"]["tokens"] == 999


def test_property_risk_raises_profile_never_lowers():
    assert RoutingRequest(risk="critical", profile="economy")\
        .effective_profile() == "strict"
    assert RoutingRequest(risk="low", profile="deep")\
        .effective_profile() == "deep"


def test_property_unknown_tokens_not_zero(tmp_path):
    led = TokenLedger(tmp_path)
    led.record(LedgerEntry(operation="m", token_basis="unknown"))
    rep = led.report()
    assert rep["basis_counts"]["unknown"] == 1
    assert rep["input_tokens_observed"] == 0   # absent, not fabricated


def test_property_essential_never_dropped(tmp_path):
    """under any budget pressure, essential evidence either fits or the
    capsule refuses — it is never silently dropped."""
    gw = ContextGateway(tmp_path / "g")
    for budget in (10, 50, 500, 50000):
        res = gw.build(ContextRequest(
            task="sec", essential_bytes=1000, budget_bytes=budget,
            facts=[{"fact_id": "sec1", "kind": "security"}]))
        if "refusal" not in res:
            assert budget >= 1000


def test_property_provider_calls_hard_limit():
    env = BudgetEnvelope(limits={"provider_calls": Limit(hard=0)})
    v = env.check("provider_calls", 1)
    assert v.decision == "hard_exceeded"
    assert env.check("provider_calls", 0).decision == "ok"


def test_property_fanout_bounded_by_envelope():
    env = BudgetEnvelope(limits={"agents": Limit(hard=2)})
    assert env.check("agents", 2).decision == "ok"
    assert env.check("agents", 3).decision == "hard_exceeded"


def test_property_verification_floor_survives_budget_pressure():
    plan = VerificationPlanner().plan(risk="high", budget_pressure=True,
                                      touches_security=True)
    assert "security-verification" in plan.checks
    assert plan.floor == "V3-integration"   # high-risk floor unmoved


def test_property_evidence_gate_never_calls_when_local_suffices():
    for cov in (0.5, 0.7, 1.0):
        r = evidence_gate("q", {"answers": ["a"], "coverage": cov})
        assert r["decision"] == "refuse_live_call"


# --- adversarial E1–E12 --------------------------------------------------------

def test_e1_stale_cache_rejected(tmp_path):
    s = CacheStore(tmp_path / "c")
    s.put("finding", "f", 1, {"rule_catalog_hash": "v1"})
    dec, _ = s.get("finding", "f", {"rule_catalog_hash": "v2"})
    assert dec.state != "hit"


def test_e2_rule_change_transitive(tmp_path):
    """rule change → findings+analysis miss; artifacts+facts still hit."""
    s = CacheStore(tmp_path / "c")
    s.put("artifact", "a", 1, {"runtime_version": "r"})
    s.put("fact", "f", 1, {"artifact_hash": "ah"})
    s.put("finding", "fd", 1, {"rule_catalog_hash": "v1"})
    s.put("analysis", "an", 1, {"rule_catalog_hash": "v1"})
    new = {"runtime_version": "r", "artifact_hash": "ah",
           "rule_catalog_hash": "v2"}
    assert s.get("artifact", "a", new)[0].state == "hit"
    assert s.get("fact", "f", new)[0].state == "hit"
    assert s.get("finding", "fd", new)[0].state != "hit"
    assert s.get("analysis", "an", new)[0].state != "hit"


def test_e3_essential_evidence_survives_pressure(tmp_path):
    gw = ContextGateway(tmp_path / "g")
    res = gw.build(ContextRequest(
        task="security", scope="repository", essential_bytes=900,
        budget_bytes=10_000,
        facts=[{"fact_id": "sec1", "kind": "security"}]))
    if "refusal" not in res:
        assert "sec1" in str(res["capsule"]["facts"])


def test_e4_resume_no_downgrade(tmp_path):
    st = CheckpointStore(tmp_path / "ck")
    st.save(EconomyCheckpoint(run_id="r", routing_profile="deep"))
    res = st.resume("r", current_deps={}, requested_profile="economy")
    assert res["refusal"] == "PF-CHECKPOINT-DOWNGRADE"


def test_e5_fanout_under_envelope():
    env = BudgetEnvelope(limits={"agents": Limit(hard=2),
                                 "parallelism": Limit(hard=2)})
    assert env.check("agents", 2).decision == "ok"
    assert env.check("agents", 3).decision == "hard_exceeded"


def test_e6_security_not_dropped_for_economy():
    """a critical+security change keeps its floor even under pressure."""
    plan = VerificationPlanner().plan(risk="critical",
                                      touches_security=True,
                                      budget_pressure=True)
    assert "security-verification" in plan.checks
    assert plan.floor == "V4-runtime"


def test_e7_debate_rounds_bounded():
    res = run_debate("x?", positions=[
        {"agent": "a", "claim": "y", "evidence": ["e0"], "round": 0},
        {"agent": "a", "claim": "y", "evidence": ["e99"],
         "round": 10},                     # beyond bound → refuse
    ], max_rounds=3)
    assert "refusal" in res


def test_e8_unknown_tokens_stay_unknown(tmp_path):
    led = TokenLedger(tmp_path)
    led.record(LedgerEntry(operation="m", token_basis="unknown"))
    rep = led.report()
    assert rep["input_tokens_observed"] == 0
    assert rep["basis_counts"]["unknown"] == 1


def test_e9_fleet_delta_minimal():
    a = {"members": {f"m{i}": "r1" for i in range(50)}}
    b = {"members": {**a["members"], "m0": "r2"}}
    d = fleet_delta(a, b)
    assert d["changed"] == ["m0"] and d["unchanged"] == 49


def test_e10_challenger_no_autopromote():
    v = promote_verdict(
        champion={"id": "champ"},
        challenger={"id": "chall", "quality_pass": True,
                    "safety_unchanged": True, "economy_better": True},
        human_approved=False)
    assert v["verdict"] == "awaiting_human" and v["champion_kept"]


def test_e11_context_ref_is_pointer_not_payload(tmp_path):
    cap = ContextCapsule(task="t", summary="s",
                         facts=[{"fact_id": "f1", "v": "x" * 500}])
    ref = cap.ref()
    assert ref.startswith("context://sha256/")
    assert len(ref) < 100                # pointer, never payload


def test_e12_provider_calls_hard_limit_zero():
    env = BudgetEnvelope(limits={"provider_calls": Limit(hard=0)})
    assert env.check("provider_calls", 1).decision == "hard_exceeded"


# --- doctor checks ------------------------------------------------------------

def test_doctor_duplicate_tool_call_detected(tmp_path):
    """waste detector reads the economy ledger and flags duplicates."""
    import json

    from platformforge.economy.waste import EconomyWasteDetector
    d = tmp_path / ".platformforge" / "ledger"
    d.mkdir(parents=True)
    rows = [{"entry_type": "tool", "tool": "kubectl", "input_bytes": 512}
            for _ in range(3)]
    (d / "economy.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows))
    rep = EconomyWasteDetector(tmp_path).detect()
    kinds = {f["waste_type"] for f in rep["waste_findings"]}
    assert "duplicate_tool_call" in kinds
