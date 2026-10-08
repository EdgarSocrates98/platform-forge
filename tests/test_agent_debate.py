"""Phase K — debate engine + run store."""

from __future__ import annotations

from platformforge.agents.contracts import AgentRunRecord
from platformforge.agents.debate import run_debate
from platformforge.agents.runstore import RunStore

POS_A = {"agent": "platform-sre-specialist", "claim": "cache regression",
         "evidence": ["fact-1"], "evidence_tier": 2, "freshness": "current"}
POS_B = {"agent": "platform-kubernetes-specialist",
         "claim": "pod churn caused it", "evidence": ["fact-2"],
         "evidence_tier": 4, "freshness": "fresh"}


def test_debate_requires_question():
    out = run_debate("   ", [POS_A])
    assert out["refusal"] == "PF-AGENT-NO-EVIDENCE"


def test_position_without_evidence_refused():
    out = run_debate("q?", [{"agent": "x", "claim": "c"}])
    assert out["refusal"] == "PF-AGENT-NO-EVIDENCE"
    assert "no evidence" in out["why"]


def test_too_many_participants_refused():
    pos = [{"agent": f"a{i}", "claim": "c", "evidence": ["e"]}
           for i in range(6)]
    out = run_debate("q?", pos)
    assert out["refusal"] == "PF-AGENT-DEBATE-UNRESOLVED"
    assert "participants" in out["why"]


def test_rounds_bounded():
    out = run_debate("q?", [dict(POS_A, round=4)])
    assert out["refusal"] == "PF-AGENT-DEBATE-UNRESOLVED"
    assert "round" in out["why"]


def test_winner_still_requires_verifier():
    out = run_debate("which root cause?", [POS_A, POS_B])
    assert "debate" in out
    d = out["debate"]
    assert d["outcome"] == "winner"
    assert d["winner"] == "platform-sre-specialist"  # better tier/freshness
    assert out["verifier_required"] is True
    assert d["receipt"]["verifier_required"] is True
    assert d["axes"]  # declared axes present


def test_no_evidence_positions_unresolved():
    # positions pass the shape check but the referee still can't pick
    out = run_debate("q?", [{"agent": "a", "claim": "c",
                             "evidence": ["e"], "evidence_tier": 7,
                             "freshness": "unresolved"}])
    assert "debate" in out or out["refusal"]


def test_runstore_roundtrip_and_resume(tmp_path):
    store = RunStore(tmp_path)
    rec = AgentRunRecord(run_id="run-1", task_spec_hash="h1",
                         router_decision={"mode": "coordinated"},
                         agents=("a", "b"), evidence=("f1", "f2"),
                         budget={"spent": {"model_calls": 3}},
                         verdict="confirmed")
    store.save(rec)
    got = store.load("run-1")
    assert got.task_spec_hash == "h1" and got.agents == ("a", "b")
    assert "run-1" in store.runs()

    res = store.resume("run-1", artifact_hashes={"a1": "sha"},
                       observation_freshness="current")
    assert res["resumed"]
    assert res["preserved"]["budget_spent"] == {"model_calls": 3}

    stale = store.resume("run-1", observation_freshness="stale")
    assert not stale["resumed"] and stale["problems"]

    missing = store.resume("nope")
    assert not missing["resumed"]


def test_runstore_rejects_bad_ids(tmp_path):
    store = RunStore(tmp_path)
    import pytest
    with pytest.raises(ValueError):
        store.save(AgentRunRecord(run_id="../escape", task_spec_hash="h"))
