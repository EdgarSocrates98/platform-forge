"""Phase L — agent adversarial review A1–A12 (§185–196).

Each test answers a hostile question with a deterministic probe over the
real machinery — not a doc claim. Every answer is expected NO.
"""

from __future__ import annotations

import yaml

from platformforge.agents.contracts import AgentRunRecord, envelope_for
from platformforge.agents.debate import run_debate
from platformforge.agents.mirrors import render
from platformforge.agents.orchestrator import build_dag, load_loops
from platformforge.agents.planner import plan
from platformforge.agents.roster import AGENTS
from platformforge.agents.specialists import finding
from platformforge.agents.verifier import verify_run
from platformforge.routing import TaskSignal, route


def test_a1_agent_cannot_fabricate_evidence():
    """A finding that claims `confirmed` with no evidence is demoted —
    the contract cannot mint facts."""
    f = finding("platform-sre-specialist", "fabricated", status="confirmed")
    assert f["status"] == "unsupported" and f["demoted"]


def test_a2_orchestrator_cannot_skip_verifier():
    """Every non-deterministic route carries a verifier; DAG validation
    rejects a loop without a terminal verifier."""
    sig = TaskSignal(task_type="analysis", domains=["k8s"],
                     complexity="medium")
    assert route(sig)["verifier"] == "platform-verifier"
    spec = plan("audit platform")
    for name, loop in load_loops().items():
        nodes, _missing = build_dag(loop, spec)
        assert any(n.agent == "platform-verifier" for n in nodes), name
        # nothing unconditional runs after verify — only explicit
        # gated follow-ups (e.g. optimization's conditional
        # change-intent) may follow it
        vi = max(i for i, n in enumerate(nodes)
                 if n.agent == "platform-verifier")
        for n in nodes[vi + 1:]:
            assert getattr(n, "condition", None) or n.stage.startswith(
                "change-intent"), (name, n.stage)


def test_a3_specialist_cannot_dispatch_uncontrolled_agents():
    """Specialist specs delegate to nobody — the roster is closed."""
    for name, spec in AGENTS.items():
        if spec.role == "specialist":
            assert not spec.delegates_to, name


def test_a4_critical_task_cannot_bypass_security_reviewer():
    sig = TaskSignal(task_type="change", production=True,
                     mutability="mutate", security_sensitive=True,
                     risk="critical")
    out = route(sig)
    assert out["mode"] == "critical-review"
    assert "platform-security-reviewer" in out["reviewers"]
    assert "platform-operations-safety-reviewer" in out["reviewers"]


def test_a5_mirror_cannot_gain_more_permission_than_canonical(tmp_path):
    """Mirrors render from the spec — a host file declaring extra verbs
    is drift, caught by check()."""
    from platformforge.agents.mirrors import check, sync
    sync(tmp_path)
    spec = AGENTS["platform-sre-specialist"]
    md = tmp_path / "agents" / "platform-sre-specialist.md"
    # a hand-edited mirror claiming extra verbs is stale → drift
    md.write_text(md.read_text() + "\nAllowed verbs: mutate\n")
    assert not check(tmp_path)["ok"]
    # canonical render cannot contain verbs the spec doesn't declare
    assert "mutate" not in render(spec, "md") or \
        "mutate" in " ".join(spec.allowed_verbs)


def test_a6_budget_cannot_reset_on_resume(tmp_path):
    from platformforge.agents.runstore import RunStore
    store = RunStore(tmp_path)
    store.save(AgentRunRecord(run_id="r1", task_spec_hash="h",
                              budget={"spent": {"model_calls": 5}}))
    res = store.resume("r1")
    assert res["preserved"]["budget_spent"]["model_calls"] == 5


def test_a7_debate_cannot_run_forever():
    out = run_debate("q?", [{"agent": "a", "claim": "c",
                           "evidence": ["e"], "round": 99}])
    assert out["refusal"] == "PF-AGENT-DEBATE-UNRESOLVED"


def test_a8_coordinator_cannot_execute_mutation():
    """Coordinator write_scope is never `mutate`; production mutation
    routes to the external human-gate, not to an agent."""
    for name, spec in AGENTS.items():
        if spec.role in ("coordinator", "orchestrator"):
            assert spec.write_scope != "mutate", name
    out = route(TaskSignal(task_type="change", production=True,
                           mutability="mutate"))
    stages = {s["agent"] for s in out["dag"]}
    assert "human-gate" in stages


def test_a9_verifier_cannot_verify_own_work():
    rec = AgentRunRecord(run_id="r", task_spec_hash="h",
                         agents=("platform-verifier",))
    out = verify_run(rec, producers=["platform-verifier"])
    assert out["refusal"] == "PF-AGENT-SELF-VERIFICATION"


def test_a10_context_cannot_exceed_budget_with_fleet():
    """A pack that doesn't fit reports fits=False — nothing silently
    ships the whole fleet."""
    from platformforge.agents.contextpack import build_pack
    huge = [{"node": f"n{i}", "data": "x" * 1000} for i in range(500)]
    out = build_pack("audit", evidence=huge, max_context_bytes=10_000)
    assert not out["fits"]
    env = envelope_for("tiny")
    env.charge(context_bytes=500_000)
    assert env.check()["refusal"] == "PF-AGENT-BUDGET-EXHAUSTED"


def test_a11_routing_cannot_reference_nonexistent_agent():
    from platformforge.routing import validate_routing
    out = validate_routing()
    assert out["ok"], out["problems"]


def test_a12_low_risk_task_cannot_invoke_deep_swarm():
    out = route(TaskSignal(task_type="analysis", domains=["iac"],
                           complexity="low", risk="low"))
    assert out["mode"] in ("deterministic", "single-specialist")
    assert out["budget"] in ("tiny", "small")
    assert "platform-debate-referee" not in out["reviewers"]


def test_routing_yaml_has_no_dangling_refs():
    doc = yaml.safe_load(
        __import__("pathlib").Path(
            "rules/catalog/routing.yaml").read_text())
    names = set(AGENTS)
    for r in doc.get("routes", []):
        for a in (r.get("agents", []) + r.get("add_specialists", [])
                  + r.get("add_reviewers", [])
                  + [r.get("coordinator") or ""]):
            if a and a != "human-gate":
                assert a in names, a
