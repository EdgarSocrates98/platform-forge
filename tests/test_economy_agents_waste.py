"""Agent fanout economy (§117–129), debate economy (§130–137),
waste detector (§112–116), tool output economy (§105–110),
routing contracts (§138–160)."""

from __future__ import annotations

from platformforge.agents.debate import build_referee_packet, run_debate
from platformforge.agents.uniqueness import (
    AgentContribution,
    AgentUniqueness,
    fanout_verdict,
    suggested_fanout,
)
from platformforge.economy.ledger import EconomyLedger, ToolUsageEntry
from platformforge.economy.waste import EconomyWasteDetector
from platformforge.routing.decision import (
    PROFILE_DEFAULTS,
    RoutingDecision,
    RoutingRequest,
    decision_receipt_link,
    promote_verdict,
    receipt,
)


class TestUniqueness:
    def test_unique_vs_duplicated(self):
        u = AgentUniqueness(run_id="r1").audit([
            AgentContribution("a", ["F1", "F2"]),
            AgentContribution("b", ["F2", "F3"]),
            AgentContribution("c", ["F1"])])   # all duplicated
        assert u.unique_contribution["b"] == ["F3"]
        assert u.duplicated_contribution["c"] == ["F1"]
        assert any(f["agent"] == "c" for f in u.findings)

    def test_zero_contribution_flagged(self):
        u = AgentUniqueness(run_id="r1").audit([
            AgentContribution("idle-agent", [])])
        assert u.findings[0]["waste_type"] == "unused_agent"

    def test_selective_agentics(self):
        assert suggested_fanout("lint", ["iac"], "low")[
            "suggested_max_agents"] == 0
        assert suggested_fanout("analysis", ["a", "b", "c"], "low")[
            "mode"] == "multi-specialist"
        assert suggested_fanout("analysis", ["a"], "critical")[
            "mode"] == "debate-or-review"

    def test_fanout_never_exceeds_envelope(self):
        out = fanout_verdict({}, 5, 3)
        assert out["refusal"] == "PF-ECONOMY-BUDGET-EXHAUSTED"
        assert fanout_verdict({}, 2, 3)["decision"] == "ok"


class TestDebateEconomy:
    def test_referee_packet_no_transcript(self):
        pkt = build_referee_packet([
            {"agent": "a", "claim": "use X", "evidence": ["e1", "e2"]},
            {"agent": "b", "claim": "use Y", "evidence": ["e2", "e3"]}])
        assert pkt["shared_evidence"] == ["e2"]
        assert pkt["deltas"][0]["own_evidence"] == ["e1"]
        assert "transcript" not in pkt

    def test_stagnation_stops_rounds(self):
        out = run_debate("which?", [
            {"agent": "a", "claim": "X", "evidence": ["e1"], "round": 0},
            {"agent": "b", "claim": "Y", "evidence": ["e2"], "round": 0},
            {"agent": "a", "claim": "X!", "evidence": ["e1"], "round": 1},
            # round 1 adds no new evidence ids → stop before adjudicating it
        ])
        assert out["debate"]["stopped_early"]
        assert out["debate"]["stagnant_round"] == 1

    def test_progressing_rounds_not_trimmed(self):
        out = run_debate("which?", [
            {"agent": "a", "claim": "X", "evidence": ["e1"], "round": 0},
            {"agent": "b", "claim": "Y", "evidence": ["e2"], "round": 0},
            {"agent": "a", "claim": "X refined",
             "evidence": ["e1", "e9"], "round": 1}])
        assert not out["debate"]["stopped_early"]


class TestWasteDetector:
    def test_duplicate_tool_call_detected(self, tmp_path):
        led = EconomyLedger(tmp_path)
        for _ in range(3):
            led.record(ToolUsageEntry(tool="graph.blast",
                                      input_bytes=500, run_id="r1"))
        out = EconomyWasteDetector(tmp_path).detect()
        types = {f["waste_type"] for f in out["waste_findings"]}
        assert "duplicate_tool_call" in types

    def test_empty_ledgers_no_findings(self, tmp_path):
        out = EconomyWasteDetector(tmp_path).detect()
        assert out["waste_findings"] == []


class TestToolEconomyReceipt:
    def test_receipt_measures(self, tmp_path):
        from platformforge.core.store import ArtifactStore
        from platformforge.rtk.compact import compact_output, tool_economy_receipt
        store = ArtifactStore(tmp_path / ".platformforge" / "artifacts")
        raw = "\n".join(f"line {i}" for i in range(500))
        res = compact_output("pytest -q", raw, store=store)
        r = tool_economy_receipt("pytest -q", res,
                               raw_bytes=len(raw.encode()))
        assert r["raw_bytes"] > r["compact_bytes"]
        assert r["raw_artifact"].startswith("artifact://sha256/")


class TestRoutingControlPlane:
    def test_risk_raises_profile_floor(self):
        r = RoutingRequest(task="t", profile="economy", risk="critical")
        assert r.effective_profile() == "strict"
        r2 = RoutingRequest(task="t", profile="deep", risk="low")
        assert r2.effective_profile() == "deep"

    def test_offline_no_provider_calls(self):
        assert PROFILE_DEFAULTS["offline"]["provider_calls_hard"] == 0
        assert PROFILE_DEFAULTS["economy"]["provider_calls_hard"] == 0

    def test_receipt_binds_inputs_and_policy(self):
        req = RoutingRequest(task="t", signal={"domains": ["iac"]})
        dec = RoutingDecision(mode="single-specialist",
                              agents=["platform-iac-specialist"],
                              reason="single domain",
                              policy_version="routing-v2")
        rc = receipt(req, dec, {"estimated": {"model_calls": 1}})
        assert rc["policy_version"] == "routing-v2"
        assert len(rc["inputs_hash"]) == 64

    def test_challenger_needs_human_gate(self):
        champ = {"id": "route-v2"}
        chall = {"id": "route-v3", "quality_pass": True,
                 "safety_unchanged": True, "economy_better": True}
        out = promote_verdict(champ, chall)
        assert out["verdict"] == "awaiting_human"
        assert out["champion_kept"]
        out2 = promote_verdict(champ, chall, human_approved=True)
        assert out2["verdict"] == "promotable"

    def test_challenger_failing_gate_rejected(self):
        out = promote_verdict({}, {"quality_pass": False,
                                   "safety_unchanged": True,
                                   "economy_better": True})
        assert out["verdict"] == "rejected"

    def test_decision_receipt_links(self):
        link = decision_receipt_link(
            {"state": "hit"}, "context://sha256/" + "a" * 64,
            {"policy_version": "v"}, {"floor": "V2"}, {"decision": "ok"})
        assert link["schema"] == "platformforge/decision-receipt/v1"
        assert link["context_ref"].startswith("context://")
