"""Phase J — agent economy: context packs, delta context, run ledger."""

from __future__ import annotations

import pytest

from platformforge.agents.contextpack import AgentContextPack, build_pack, delta_pack
from platformforge.agents.contracts import BUDGET_CLASSES, envelope_for
from platformforge.agents.runledger import AgentRunLedger, AgentRunRow


def test_budget_classes_ordered():
    order = ["tiny", "small", "standard", "deep", "critical"]
    assert list(BUDGET_CLASSES) == order
    ctx = [BUDGET_CLASSES[k].max_context_bytes for k in order]
    assert ctx == sorted(ctx)


def test_pack_measured_and_addressed():
    pack = AgentContextPack(
        task_summary="audit iac", evidence=[{"fact_id": "f1"}],
        open_questions=["who owns this?"])
    assert pack.byte_size == len(pack.serialize())
    assert pack.content_hash == AgentContextPack(
        task_summary="audit iac", evidence=[{"fact_id": "f1"}],
        open_questions=["who owns this?"]).content_hash
    assert pack.fits(1_000_000)["fits"]


def test_build_pack_drops_optional_before_essential():
    big_ops = [{"op": f"op{i}", "data": "x" * 500} for i in range(20)]
    out = build_pack("t", evidence=[{"fact_id": "f1"}],
                     recent_operations=big_ops, max_context_bytes=2000)
    assert "recent_operations" in out["dropped_optional"]
    assert out["pack"]["evidence"] == [{"fact_id": "f1"}]


def test_build_pack_refuses_to_truncate_essential():
    huge_q = ["q" * 5000]
    out = build_pack("t", open_questions=huge_q, max_context_bytes=100)
    assert not out["fits"]
    assert "narrow the task" in out["note"]


def test_delta_pack_only_ships_changes():
    base = AgentContextPack(task_summary="t", evidence=[{"fact_id": "f1"}],
                            open_questions=["q1"])
    cur = AgentContextPack(task_summary="t",
                           evidence=[{"fact_id": "f1"}, {"fact_id": "f2"}],
                           open_questions=["q1"])
    d = delta_pack(base.content_hash, base.to_dict(), cur)
    assert d["base_hash"] == base.content_hash
    assert d["delta"]["evidence"] == [{"fact_id": "f2"}]
    assert "open_questions" not in d["delta"]
    assert d["savings_pct"] > 0


def test_run_ledger_accounts(tmp_path):
    led = AgentRunLedger(tmp_path)
    led.record(AgentRunRow(run_id="r1", agent="platform-sre-specialist",
                           mode="single-specialist", model_calls=2,
                           context_bytes=3000, tool_calls=5,
                           duration_ms=120.0))
    led.record(AgentRunRow(run_id="r1", agent="platform-orchestrator",
                           mode="coordinated", agents=6, fanout=4,
                           model_calls=9, context_bytes=21000))
    rep = led.report()
    assert rep["runs"] == 2 and rep["agents_invoked"] == 7
    assert rep["model_calls"] == 11
    assert rep["by_mode"]["coordinated"]["runs"] == 1


def test_observed_rows_need_transcript(tmp_path):
    with pytest.raises(ValueError):
        AgentRunRow(run_id="r", agent="a", token_basis="observed")


def test_envelope_classes_carry_through():
    env = envelope_for("tiny")
    assert env.max_context_bytes == 24_000
    assert env.max_model_calls < envelope_for("deep").max_model_calls
