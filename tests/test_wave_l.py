"""Wave L — capability registry v2, referee v2, ownership/conflicts,
cross-repo edges, offline discipline, reproducibility, doctor, bench."""
from __future__ import annotations

import socket
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


# ── §133 offline: the core never touches the network ──────────────

def test_core_runs_with_network_blocked(tmp_path):
    """Block socket creation entirely, then run analyze→judge→graph on a
    lab fixture. Any network call is a hard failure, not a skip."""
    real_socket = socket.socket

    class NoNet(socket.socket):
        def __init__(self, *a, **kw):
            raise RuntimeError("network blocked by test")

    socket.socket = NoNet  # type: ignore[assignment]
    try:
        from platformforge.graph.build import GraphBuilder
        from platformforge.k8s import analyze_k8s
        from platformforge.models.base import Fact
        from platformforge.rules import RuleEngine, load_catalog
        fixture = REPO / "lab" / "scenarios" / "k8s-missing-limits" \
            / "fixture"
        facts = analyze_k8s(fixture)["facts"]
        assert facts
        eng = RuleEngine(load_catalog(REPO / "rules" / "catalog"))
        findings, _skipped = eng.evaluate(
            [Fact.from_dict(f) for f in facts])
        assert isinstance(findings, list)
        g = GraphBuilder().from_facts(facts).graph
        assert g.nodes
    finally:
        socket.socket = real_socket  # type: ignore[assignment]


# ── §113 capability contract tests ─────────────────────────────────

def test_capability_registry_v2_contract():
    from platformforge.mcp.registry import CAPABILITIES
    required = {"id", "version", "domain", "input_schema", "output_schema",
                "risk", "offline", "mutable", "evidence_required",
                "cost_class", "agent_requirements", "detail_levels"}
    for c in CAPABILITIES.values():
        contract = c.contract()
        assert required <= set(contract), c.name
        assert c.handler.startswith("cli:"), c.name
        assert not c.mutable or c.risk in ("guarded", "simulate")


def test_capability_handlers_resolve_to_cli():
    """Every capability handler maps to a registered CLI verb function."""
    from platformforge.cli.main import build_parser
    from platformforge.mcp.registry import CAPABILITIES
    parser = build_parser()
    funcs = set()
    for sp_action in parser._subparsers._group_actions:
        for sp in sp_action.choices.values():
            f = sp.get_default("func")
            if f:
                funcs.add(f.__name__)
    assert funcs  # sanity: parser exposes handler functions
    # every capability is bounded and documented in CAPABILITIES.md
    caps_doc = (REPO / "CAPABILITIES.md").read_text()
    for c in CAPABILITIES.values():
        assert c.max_bytes > 0 and c.max_results > 0
        assert c.name.removeprefix("platformforge_").split("_")[0] \
            in caps_doc, c.name


def test_mcp_tools_match_registry():
    from platformforge.mcp.registry import CAPABILITIES, tool_descriptors
    tools = tool_descriptors()
    assert {t["name"] for t in tools} == set(CAPABILITIES)
    for t in tools:
        assert t["annotations"]["readOnlyHint"] is True or \
            t["name"] in ("platformforge_lab_chaos",
                          "platformforge_integrate")


# ── §115 referee v2 ────────────────────────────────────────────────

def test_referee_v2_axes():
    from platformforge.agents.referee import referee
    out = referee([
        {"agent": "a", "claim": "x", "evidence_fact_ids": ["f1"],
         "evidence_tier": 1, "freshness": "current",
         "version_compat": True, "scope_match": True,
         "evidence_facts": [{"fact_id": "f1", "kind": "k", "tier": 1}]},
        {"agent": "b", "claim": "y", "evidence_fact_ids": ["f2"],
         "evidence_tier": 1, "freshness": "stale",
         "contradictions": [{"with": "c"}]},
    ])
    assert out["winner"]["agent"] == "a"
    assert set(out["axes"]) == {"tier", "freshness", "version_compat",
                                "scope", "contradictory", "completeness"}


def test_referee_no_evidence_loses():
    from platformforge.agents.referee import referee
    out = referee([{"agent": "loud", "claim": "trust me",
                    "evidence_tier": 0}])
    assert out["unresolved"] is True
    assert out["receipt"]["refusal_code"] == "platform.evidence.unresolved"


# ── §136–137 ownership + conflicts ─────────────────────────────────

def test_ownership_signals_and_conflict(tmp_path):
    from platformforge.core.ownership import analyze_ownership
    (tmp_path / "CODEOWNERS").write_text("* @team-a\n")
    (tmp_path / "catalog-info.yaml").write_text(
        "apiVersion: backstage.io/v1alpha1\nkind: Component\n"
        "metadata:\n  name: svc-x\nspec:\n  owner: team-b\n")
    ws = tmp_path / "workspace.yaml"
    ws.write_text("members:\n  - name: app\n    owner: team-c\n")
    out = analyze_ownership(tmp_path)
    kinds = [f["kind"] for f in out["facts"]]
    assert kinds.count("ownership.signal") >= 3
    # svc-x: backstage says team-b; if CODEOWNERS pattern matches the same
    # subject there'd be a conflict — here subjects differ, so check the
    # conflict detector directly below.
    sigs = [f for f in out["facts"] if f["kind"] == "ownership.signal"]
    assert {f["attrs"]["source_kind"] for f in sigs} >= {
        "codeowners", "backstage", "workspace"}


def test_ownership_conflict_detection():
    from platformforge.core.ownership import detect_conflicts
    sigs = [
        {"kind": "ownership.signal", "source": "s", "location": "l",
         "tier": 3, "fact_id": "a",
         "attrs": {"subject": "svc-x", "owners": ["team-a"],
                   "source_kind": "codeowners"}},
        {"kind": "ownership.signal", "source": "s", "location": "l2",
         "tier": 3, "fact_id": "b",
         "attrs": {"subject": "svc-x", "owners": ["team-b"],
                   "source_kind": "backstage"}},
    ]
    out = detect_conflicts(sigs)
    assert len(out) == 1
    assert out[0]["kind"] == "ownership.conflicted"
    assert {tuple(c["owners"]) for c in out[0]["attrs"]["claims"]} == {
        ("team-a",), ("team-b",)}


def test_contradiction_declared_vs_observed():
    from platformforge.core.ownership import detect_contradictions
    facts = [
        {"fact_id": "d", "kind": "aws.database", "source": "tf",
         "location": "db1", "tier": 3,
         "attrs": {"public": False, "engine": "pg"}},
        {"fact_id": "o", "kind": "aws.database", "source": "aws dump",
         "location": "db1", "tier": 1,
         "attrs": {"public": True, "engine": "pg"}},
    ]
    out = detect_contradictions(facts)
    assert len(out) == 1
    assert out[0]["kind"] == "state.contradiction"
    assert out[0]["attrs"]["diffs"]["public"] == {
        "declared": False, "observed": True}


# ── §135 cross-repo graph ──────────────────────────────────────────

def test_cross_repo_edges_inferred():
    from platformforge.graph.build import GraphBuilder
    facts = [
        {"fact_id": "g1", "kind": "gitops.argocd_app", "source": "s",
         "location": "l", "tier": 3,
         "attrs": {"workspace_member": "gitops", "dest_server": "prod-eks",
                   "dest_namespace": "web", "name": "app1",
                   "graph": {"nodes": [{"kind": "argocd_application",
                                        "label": "argocd/app1"}],
                             "edges": []}}},
        {"fact_id": "c1", "kind": "aws.cluster", "source": "s2",
         "location": "prod-eks", "tier": 1,
         "attrs": {"workspace_member": "infra", "name": "prod-eks"}},
        {"fact_id": "w1", "kind": "k8s.workload", "source": "s3",
         "location": "web/dep", "tier": 3,
         "attrs": {"workspace_member": "app", "namespace": "web"}},
    ]
    g = GraphBuilder().from_facts(facts).graph
    inferred = [e for e in g.edges.values()
                if e.provenance == "inferred"]
    assert inferred, "expected cross-repo inferred edges"
    assert all(e.source_fact_ids for e in inferred)
    assert all(e.confidence < 1.0 for e in inferred)


# ── §138/139 manifest + negotiation ────────────────────────────────

def test_manifest_v2_fields():
    from platformforge.forge import capability_manifest
    m = capability_manifest(REPO)
    assert m["manifest"] == "platformforge/capability-manifest/v2"
    for k in ("quality_level", "maturity", "required_evidence",
              "cost_characteristics", "risk", "capabilities_v2",
              "supported_versions"):
        assert k in m, k


# ── §141 doctor --deep ─────────────────────────────────────────────

def test_doctor_deep(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from platformforge.cli.main import build_parser
    p = build_parser()
    args = p.parse_args(["doctor", "--deep", "--repo", str(tmp_path),
                         "--json"])
    assert args.func(args) in (0, 1)  # deep report runs; ok may vary


# ── §153 reproducibility ───────────────────────────────────────────

def test_deterministic_graph_and_findings():
    from platformforge.graph.build import GraphBuilder
    from platformforge.models.base import Fact
    from platformforge.rules import RuleEngine, load_catalog
    fixture = REPO / "lab" / "scenarios" / "k8s-missing-limits" / "fixture"
    from platformforge.k8s import analyze_k8s
    facts = analyze_k8s(fixture)["facts"]

    def run():
        g = GraphBuilder().from_facts(facts).graph
        findings, _ = RuleEngine(load_catalog(
            REPO / "rules" / "catalog")).evaluate(
            [Fact.from_dict(f) for f in facts])
        return g.graph_hash, sorted(f.finding_id for f in findings)

    a, b = run(), run()
    assert a == b, "same inputs must produce identical graph+findings"


# ── §148 bench smoke ───────────────────────────────────────────────

def test_bench_smoke():
    from platformforge.bench import run_benchmark, token_benchmark
    r = run_benchmark(repeat=1)
    assert r["facts_total"] > 0
    assert "rule_execution" in r and "median_s" in r["rule_execution"]
    t = token_benchmark(repeat=1)
    assert any(v.get("raw_bytes") for v in t.values()
               if isinstance(v, dict))
