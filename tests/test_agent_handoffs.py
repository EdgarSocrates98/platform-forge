"""cycle5.1 §71–73 — every handoff is structured; refs travel, raw
context bodies do not."""

import json

from platformforge.agents import AgentHandoff
from platformforge.agents.contracts import doc_hash
from platformforge.resources import data_path


def test_handoff_schema_roundtrip():
    h = AgentHandoff(sender="platform-orchestrator", to="platform-iac-specialist",
                     task_id="t1", reason="iac domain slice",
                     completed=("inventory",),
                     evidence=("PF-IAC-1", "artifact:sha256:abc"),
                     open_questions=("module ownership?",),
                     budget_spent={"context_bytes": 1200},
                     budget_remaining={"context_bytes": 118800},
                     next_required_capability="platform.analyze.iac",
                     context_pack_ref="sha256:pack")
    d = h.to_dict()
    assert d["from"] == "platform-orchestrator"  # yaml key per §72
    schema = json.loads((data_path("contracts") /
                         "agent-handoff.schema.json").read_text())
    import jsonschema
    errs = [e.message for e in
            jsonschema.Draft7Validator(schema).iter_errors(d)]
    assert errs == []
    h2 = AgentHandoff.from_dict(d)
    assert h2.sender == "platform-orchestrator"
    assert h2.evidence == ("PF-IAC-1", "artifact:sha256:abc")


def test_handoff_carries_refs_not_bodies(tmp_path):
    h = AgentHandoff(sender="pf-extractor", to="pf-judge", task_id="t2",
                     evidence=("PF-K8S-1",))
    blob = json.dumps(h.to_dict())
    # a 1MB artifact body must not ride inside a handoff (§73)
    assert len(blob) < 8192
    assert h.context_pack_ref == "" or h.context_pack_ref.startswith(
        ("sha256:", "pack:"))


def test_handoff_preserves_budget_continuity():
    """§72: spent + remaining both travel — a receiver never sees a
    reset budget."""
    spent = {"model_calls": 3, "context_bytes": 5000}
    remaining = {"model_calls": 5, "context_bytes": 115000}
    h = AgentHandoff(sender="a", to="b", task_id="t",
                     budget_spent=spent, budget_remaining=remaining)
    d = h.to_dict()
    assert d["budget_spent"] == spent
    assert d["budget_remaining"] == remaining
    # deterministic identity for audit
    assert doc_hash(h.to_dict()) == doc_hash(
        AgentHandoff.from_dict(h.to_dict()).to_dict())
