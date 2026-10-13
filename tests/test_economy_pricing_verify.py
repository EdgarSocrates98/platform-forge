"""Provider pricing (§89–96) + selective verification (§97–104)."""

from __future__ import annotations

import datetime as dt

from platformforge.economy.pricing import cost, load_pricing, rate_for
from platformforge.economy.verifyplan import RISK_FLOORS, TIERS, VerificationPlanner


def _write_catalog(tmp_path):
    p = tmp_path / "pricing.yaml"
    p.write_text("""pricing:
  - provider: anthropic
    model: claude-x
    effective_at: "2026-01-01"
    currency: USD
    input_per_million: 3.0
    output_per_million: 15.0
    source: declared-test
  - provider: anthropic
    model: claude-x
    effective_at: "2026-03-01"
    input_per_million: 2.0
    output_per_million: 10.0
    source: declared-test-v2
""")
    return p


class TestPricing:
    def test_load_declared_catalog(self, tmp_path):
        cat = load_pricing(_write_catalog(tmp_path))
        assert len(cat) == 2 and cat[0].provider == "anthropic"

    def test_missing_catalog_empty_not_error(self, tmp_path):
        assert load_pricing(tmp_path / "nope.yaml") == ()

    def test_missing_rate_refuses(self, tmp_path):
        cat = load_pricing(_write_catalog(tmp_path))
        out = rate_for(cat, "aws", "ec2")
        assert out["refusal"] == "PF-ECONOMY-PRICING-MISSING"

    def test_effective_date_selects(self, tmp_path):
        cat = load_pricing(_write_catalog(tmp_path))
        old = rate_for(cat, "anthropic", "claude-x",
                       at=dt.datetime(2026, 2, 1,
                                      tzinfo=dt.timezone.utc))
        assert old["rate"]["input_per_million"] == 3.0
        new = rate_for(cat, "anthropic", "claude-x",
                       at=dt.datetime(2026, 4, 1,
                                      tzinfo=dt.timezone.utc))
        assert new["rate"]["input_per_million"] == 2.0

    def test_cost_priced(self, tmp_path):
        cat = load_pricing(_write_catalog(tmp_path))
        out = cost(cat, "anthropic", "claude-x", 1_000_000, 100_000,
                   at=dt.datetime(2026, 4, 1, tzinfo=dt.timezone.utc))
        assert out["state"] == "priced"
        assert out["cost_usd"] == 3.0     # 2.0 + 1.0

    def test_unobserved_tokens_unresolved(self, tmp_path):
        cat = load_pricing(_write_catalog(tmp_path))
        out = cost(cat, "anthropic", "claude-x", None, None)
        assert out["state"] == "unresolved"
        assert out["code"] == "PF-ECONOMY-USAGE-UNOBSERVED"

    def test_no_rate_not_zero(self, tmp_path):
        out = cost(load_pricing(tmp_path / "none.yaml"),
                   "aws", "x", 100, 50)
        assert out["state"] == "unresolved"
        assert "cost_usd" not in out or out.get("cost_usd") is None

    def test_malformed_row_refused(self, tmp_path):
        p = tmp_path / "bad.yaml"
        p.write_text("pricing:\n  - provider: x\n")
        import pytest
        with pytest.raises(ValueError):
            load_pricing(p)


class TestVerificationPlanner:
    def test_risk_floors(self):
        vp = VerificationPlanner()
        assert vp.plan(risk="low").floor == "V0-static"
        assert vp.plan(risk="high").floor == "V3-integration"
        assert vp.plan(risk="critical").floor == "V4-runtime"

    def test_security_change_always_includes_security(self):
        vp = VerificationPlanner()
        p = vp.plan(risk="low", touches_security=True)
        assert "security-verification" in p.checks

    def test_graph_aware_raise(self):
        vp = VerificationPlanner()
        assert vp.plan(risk="low", impacted_nodes=500).floor == "V2-unit"
        assert vp.plan(risk="low", change_scope="platform").floor == \
            "V3-integration"

    def test_budget_cannot_lower_floor(self):
        vp = VerificationPlanner()
        p = vp.plan(risk="critical", budget_pressure=True)
        assert p.floor == "V4-runtime"
        assert "budget" in p.reasons

    def test_ledger_records_skipped(self, tmp_path):
        vp = VerificationPlanner(tmp_path)
        vp.plan(risk="medium")
        import json
        rows = (tmp_path / ".platformforge" / "ledger" /
                "verification.jsonl").read_text()
        row = json.loads(rows.splitlines()[0])
        assert "V1-contract" in row["selected"]
        assert "V4-runtime" in row["skipped"]
        assert row["reasons"]["floor"]

    def test_all_tiers_ordered(self):
        assert list(TIERS) == sorted(TIERS, key=lambda t:
                                     list(TIERS).index(t))
        assert set(RISK_FLOORS.values()) <= set(TIERS)
