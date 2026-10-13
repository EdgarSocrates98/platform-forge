"""cycle5.1 §69–70, §74–77 — agent protocol contracts: versioned schemas,
legal TaskSpec transitions, tier vocabularies, refusal namespace."""

import json

import pytest

from platformforge.agents import (
    ACCESS_TIERS,
    AGENTS,
    MODEL_TIERS,
    OUTPUT_STATUSES,
    ROUTING_MODES,
    TASK_STATES,
    AgentRefusal,
    PlatformTaskSpec,
)
from platformforge.resources import data_path

CONTRACTS = data_path("contracts")


def _schema(name: str) -> dict:
    return json.loads((CONTRACTS / name).read_text())


def _validate(doc: dict, schema_file: str) -> list[str]:
    import jsonschema
    return [e.message for e in
            jsonschema.Draft7Validator(_schema(schema_file))
            .iter_errors(doc)]


def test_vocabularies_are_closed():
    assert ACCESS_TIERS == ("read-only", "state-writer",
                            "workspace-writer", "governed-writer")
    assert "writer" not in ACCESS_TIERS  # §9 — never bare "writer"
    assert set(MODEL_TIERS) == {"deterministic", "fast", "standard",
                                "deep", "critical-review"}
    assert set(TASK_STATES) == {"draft", "reviewed", "sealed",
                                "rejected", "expired"}
    assert set(ROUTING_MODES) == {"deterministic", "single-specialist",
                                  "multi-specialist", "coordinated",
                                  "debate", "critical-review"}
    for code in AgentRefusal.ALL:
        assert code.startswith("PF-AGENT-")


def test_agent_spec_schema_validates_roster():
    errs = []
    for a in AGENTS.values():
        errs += _validate(a.to_dict(), "agent-spec.schema.json")
        errs += [f"{a.name}:{e}" for e in a.contract_errors()]
    assert errs == []


def test_taskspec_lifecycle():
    spec = PlatformTaskSpec(task_id="t1", intent="audit platform")
    assert spec.state == "draft" and spec.spec_hash.startswith("sha256:")
    errs = _validate(spec.to_dict(), "task-spec.schema.json")
    assert errs == []
    reviewed = spec.transition("reviewed", reviewer="task-spec-reviewer")
    assert reviewed.state == "reviewed" and reviewed.spec_hash != spec.spec_hash
    sealed = reviewed.transition("sealed")
    assert sealed.state == "sealed"
    with pytest.raises(ValueError):
        sealed.transition("draft")
    with pytest.raises(ValueError):
        spec.transition("sealed")  # draft cannot skip review


def test_taskspec_hash_is_content_addressed():
    a = PlatformTaskSpec(task_id="t1", intent="x")
    b = PlatformTaskSpec(task_id="t1", intent="x", created_at=a.created_at)
    assert a.spec_hash == b.spec_hash
    c = PlatformTaskSpec(task_id="t1", intent="different",
                         created_at=a.created_at)
    assert c.spec_hash != a.spec_hash


def test_every_refusal_keeps_code_and_unlock():
    from platformforge.agents.contracts import refusal
    r = refusal(AgentRefusal.NO_EVIDENCE, "no facts", "collect first")
    assert r["refusal"].startswith("PF-AGENT-")
    assert r["unlock"]


def test_output_statuses_cover_cycle5_vocabulary():
    for s in ("confirmed", "supported", "candidate", "unresolved",
              "refuted", "unsupported", "not-observed"):
        assert s in OUTPUT_STATUSES
