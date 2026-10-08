"""Phase 12 gate: roster contract, mirrors, referee, playbook.
Cycle 5.1: canonical platform-* names; legacy names resolve."""

from platformforge.agents import AGENTS, coordinator_for, playbook, referee, resolve
from platformforge.agents.mirrors import lint, sync


def test_roster_contract():
    assert lint()["ok"]
    orch = AGENTS["platform-orchestrator"]
    assert orch.role == "orchestrator" and orch.delegates_to
    for a in AGENTS.values():
        # agents propose, never mutate platform state directly
        assert a.access in ("read-only", "state-writer")
        assert a.write_scope in ("none", "runs")


def test_legacy_names_resolve():
    assert resolve("iac-analyst").name == "platform-iac-specialist"
    assert resolve("consistency-referee").name == "platform-debate-referee"
    assert resolve("no-such-agent") is None


def test_coordinator_routing():
    assert coordinator_for("k8s").name == "platform-kubernetes-specialist"
    assert coordinator_for("unknown-domain").name == "platform-orchestrator"


def test_mirrors_generated(tmp_path):
    written = sync(tmp_path)
    assert len(written[".claude/agents"]) == len(AGENTS)
    content = (tmp_path / ".claude/agents/platform-orchestrator.md").read_text()
    assert "GENERATED" in content and "## Never" in content
    toml = (tmp_path / ".codex/agents/platform-kubernetes-specialist.toml").read_text()
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
    assert pb["role"] == "orchestrator"
    assert any("route" in s["verb"] for s in pb["steps"])
    pb2 = playbook(domain="finops")
    assert pb2["agent"] == "platform-finops-specialist"


def test_playbook_unknown_agent_refuses():
    out = playbook("ghost-agent")
    assert out["refusal"] == "PF-AGENT-UNKNOWN-AGENT"
    assert out["unlock"]
