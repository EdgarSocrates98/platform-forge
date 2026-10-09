"""Economy contracts — EconomyPlan (§9–11), BudgetEnvelope (§12–24),
unified ledgers (§25–34)."""

from __future__ import annotations

import pytest

from platformforge.economy.budget import EXHAUSTED, BudgetEnvelope, Limit, phase_budgets
from platformforge.economy.ledger import (
    EconomyLedger,
    ProviderCallEntry,
    TokenAccounting,
    ToolUsageEntry,
    unified_view,
)
from platformforge.economy.plan import EconomyPlan, PlanSection


class TestEconomyPlan:
    def test_fields_and_schema(self):
        p = EconomyPlan(task="review terraform", risk="low")
        d = p.to_dict()
        assert d["schema"] == "platformforge/economy-plan/v1"
        for k in ("deterministic_reach", "cache_plan", "context_plan",
                  "routing_plan", "budget", "verification_floor",
                  "provider_call_budget", "expected_usage", "fallbacks",
                  "refusal_policy"):
            assert k in d

    def test_explain_answers_six_questions(self):
        p = EconomyPlan(
            task="t",
            deterministic_reach=PlanSection("yes", "rule-evaluable"),
            routing_plan=PlanSection("single-specialist",
                                     "cross-domain composition"),
            context_plan=PlanSection("minimal", "graph neighborhood only"))
        e = p.explain()
        for q in ("why_deterministic", "why_model", "why_multi_agent",
                  "why_this_context", "why_this_budget",
                  "why_this_provider_call"):
            assert e[q]
        assert "rule-evaluable" in e["why_deterministic"]

    def test_refusal_policy_closed_vocab(self):
        with pytest.raises(ValueError):
            EconomyPlan(refusal_policy="yolo")

    def test_routing_decision_closed_vocab(self):
        with pytest.raises(ValueError):
            EconomyPlan(routing_plan=PlanSection("swarm", "x"))

    def test_receipt_binds_plan_hash(self):
        p = EconomyPlan(task="t")
        r = p.receipt()
        assert len(r["plan_hash"]) == 64
        assert r["pipeline"][0] == "deterministic_reach"


class TestBudgetEnvelope:
    def test_dimensions_closed(self):
        with pytest.raises(ValueError):
            BudgetEnvelope(limits={"vibes": Limit(hard=1)})

    def test_hard_limit_never_exceeded(self):
        env = BudgetEnvelope(limits={"provider_calls": Limit(hard=3)})
        assert env.check("provider_calls", 3).decision == "ok"
        v = env.check("provider_calls", 4)
        assert v.decision == "hard_exceeded"
        assert v.code == EXHAUSTED
        assert v.action == "refuse"

    def test_soft_limit_crossable_with_verdict(self):
        env = BudgetEnvelope(limits={"input_tokens": Limit(soft=100)})
        v = env.check("input_tokens", 150)
        assert v.decision == "soft_exceeded"
        assert v.action == "warn"

    def test_phase_and_role_narrow_limits(self):
        env = BudgetEnvelope(
            limits={"tool_calls": Limit(hard=100)},
            phase_budgets={"verify": {"tool_calls": Limit(hard=10)}},
            role_budgets={"critic": {"tool_calls": Limit(hard=2)}})
        assert env.check("tool_calls", 50).decision == "ok"
        assert env.check("tool_calls", 11,
                         phase="verify").decision == "hard_exceeded"
        assert env.check("tool_calls", 3,
                         role="critic").decision == "hard_exceeded"

    def test_protected_items_not_reducible(self):
        env = BudgetEnvelope()
        assert not env.reducible("security_findings")
        assert not env.reducible("critical_evidence")
        assert env.reducible("supplementary_context")

    def test_protected_phases_not_removable(self):
        env = BudgetEnvelope()
        assert not env.phase_removable("VERIFY")
        assert not env.phase_removable("SECURITY")
        assert env.phase_removable("BUILD")

    def test_unknown_phase_refused(self):
        with pytest.raises(ValueError):
            BudgetEnvelope(phase_budgets={"brunch": {}})

    def test_roundtrip(self):
        env = BudgetEnvelope(
            limits={"model_calls": Limit(soft=2, hard=5)},
            role_budgets={"verifier": {"model_calls": Limit(hard=3)}})
        back = BudgetEnvelope.from_dict(env.to_dict())
        assert back.limits["model_calls"].hard == 5
        assert back.role_budgets["verifier"]["model_calls"].hard == 3

    def test_sdd_phase_split(self):
        pb = phase_budgets(1000)
        assert pytest.approx(sum(
            v["input_tokens"].soft for v in pb.values())) == 1000
        assert "VERIFY" in pb and pb["VERIFY"]["input_tokens"].soft > 0


class TestUnifiedLedger:
    def test_token_accounting_never_sums_basis(self):
        acc = TokenAccounting(observed_input_tokens=10,
                              estimated_input_tokens=5)
        d = acc.to_dict()
        assert d["basis"] == "mixed"
        assert d["total_observed"] == 10 and d["total_estimated"] == 5

    def test_tool_usage_entry(self, tmp_path):
        led = EconomyLedger(tmp_path)
        led.record(ToolUsageEntry(tool="graph.blast", calls=2,
                                  output_bytes=900, run_id="r1"))
        ents = led.entries()
        assert ents[0]["entry_type"] == "tool"
        assert ents[0]["tool"] == "graph.blast"

    def test_provider_fold_from_live(self):
        e = ProviderCallEntry.from_live_ledger(
            {"collector": "aws-ec2", "api_calls": 4, "bytes": 2048,
             "calls_by_service": {"ec2": 3, "elb": 1}, "cache_hits": 1},
            provider="aws", run_id="r1")
        assert e.api_calls == 4 and e.service == "ec2, elb"
        assert e.cost_usd is None        # unresolved until pricing declared

    def test_one_economy_view(self, tmp_path):
        from platformforge.tokensave.ledger import LedgerEntry, TokenLedger
        TokenLedger(tmp_path).record(LedgerEntry(
            operation="ctx", context_delivered=100,
            input_tokens_est=50, token_basis="estimated"))
        led = EconomyLedger(tmp_path)
        led.record(ToolUsageEntry(tool="t", input_bytes=10))
        led.record(ProviderCallEntry(provider="aws", api_calls=2))
        from platformforge.agents.runledger import AgentRunLedger, AgentRunRow
        AgentRunLedger(tmp_path).record(AgentRunRow(
            run_id="r1", agent="a", model_calls=1))
        v = unified_view(tmp_path)
        assert v["tokens"]["estimated_input_tokens"] == 50
        assert v["tools"]["calls"] == 1
        assert v["provider_calls"]["api_calls"] == 2
        assert v["provider_calls"]["cost_basis"] == "unresolved"
        assert v["agents"]["runs"] == 1
        assert v["basis_counts"]["estimated"] == 1
        assert v["basis_counts"]["unknown"] >= 1
