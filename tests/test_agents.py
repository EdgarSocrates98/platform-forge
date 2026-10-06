"""Phase 12 gate: roster contract, mirrors, referee, playbook."""

from platformforge.agents import AGENTS, coordinator_for, playbook, referee
from platformforge.agents.mirrors import lint, sync


def test_roster_contract():
    assert lint()["ok"]
    coord = AGENTS["platform-coordinator"]
    assert coord.role == "coordinator" and coord.executors
    for a in AGENTS.values():
        assert a.access == "read-only"  # agents propose, never mutate


def test_coordinator_routing():
    assert coordinator_for("k8s").name == "k8s-analyst"
    assert coordinator_for("unknown-domain").name == "platform-coordinator"


def test_mirrors_generated(tmp_path):
    written = sync(tmp_path)
    assert len(written[".claude/agents"]) == len(AGENTS)
    content = (tmp_path / ".claude/agents/platform-coordinator.md").read_text()
    assert "GENERATED" in content and "Never do" in content
    toml = (tmp_path / ".codex/agents/k8s-analyst.toml").read_text()
    assert 'role = "specialist"' in toml


def test_referee_evidence_wins():
    out = referee([
        {"agent": "a", "claim": "X", "evidence_fact_ids": ["F-1"],
         "evidence_tier": 1},
        {"agent": "b", "claim": "Y", "evidence_fact_ids": ["F-2", "F-3"],
         "evidence_tier": 5},
        {"agent": "c", "claim": "Z", "evidence_fact_ids": []},
    ])
    assert out["winner"]["agent"] == "a"  # tier-1 evidence beats more t5
    assert out["unresolved"] is False
    empty = referee([])
    assert empty["unresolved"] is True
    assert empty["receipt"]["refusal_code"] == "platform.evidence.unresolved"


def test_playbook(tmp_path):
    pb = playbook()
    assert pb["role"] == "coordinator"
    assert any("route" in s["verb"] for s in pb["steps"])
    pb2 = playbook(domain="finops")
    assert pb2["agent"] == "finops-analyst"
