"""cycle5.1 §76–77, §112, §289 — run envelopes are hard limits; exhaustion
returns PF-AGENT-BUDGET-EXHAUSTED with partial state, never silent
success, and resume never resets spend."""

from platformforge.agents import BUDGET_CLASSES, AgentRefusal, envelope_for


def test_budget_classes_bounded_and_ordered():
    assert set(BUDGET_CLASSES) == {"tiny", "small", "standard", "deep",
                                   "critical"}
    prev = None
    for cls in ("tiny", "small", "standard", "deep", "critical"):
        env = BUDGET_CLASSES[cls]
        if prev is not None:
            assert env.max_model_calls >= prev.max_model_calls
            assert env.max_context_bytes >= prev.max_context_bytes
        prev = env
    assert BUDGET_CLASSES["tiny"].max_agents == 1


def test_envelope_charges_and_exhausts():
    env = envelope_for("tiny")
    assert env.check() is None
    env.charge(model_calls=1, tool_calls=3, context_bytes=20_000)
    assert env.check() is None
    env.charge(model_calls=1)  # 2 > max 1
    r = env.check()
    assert r["refusal"] == AgentRefusal.BUDGET_EXHAUSTED
    assert r["unlock"]
    assert any("model_calls" in d for d in r["exceeded"])


def test_envelope_never_resets_on_resume():
    """§141: a restored envelope keeps spent budget."""
    env = envelope_for("small")
    env.charge(model_calls=2, context_bytes=30_000)
    snap = env.to_dict()
    from platformforge.agents import AgentRunEnvelope
    restored = AgentRunEnvelope.from_dict(snap)
    assert restored.model_calls == 2
    assert restored.context_bytes == 30_000
    assert restored.check() is None        # boundary is exclusive: 2 ≤ max
    restored.charge(model_calls=1)         # 3 > 2 — now it must refuse
    assert restored.check()["refusal"] == AgentRefusal.BUDGET_EXHAUSTED


def test_unknown_budget_class_falls_back_standard():
    env = envelope_for("nonexistent")
    assert env.max_agents == BUDGET_CLASSES["standard"].max_agents
