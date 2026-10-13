"""§91 — the offline suite must *block* remote calls, not merely avoid
them. Sockets are killed at the syscall level; any accidental network
attempt is a test failure, not a skipped feature."""

import socket

import pytest


@pytest.fixture
def no_network(monkeypatch):
    def _blocked(*a, **k):
        raise AssertionError("network access attempted in offline core")
    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(socket, "getaddrinfo", _blocked)
    return _blocked


def _facts(tmp_path):
    (tmp_path / "deploy.yaml").write_text("""
apiVersion: apps/v1
kind: Deployment
metadata: {name: api}
spec:
  template:
    spec:
      containers:
        - {name: c, image: img:1.0, securityContext: {privileged: true}}
""")
    from platformforge.k8s.manifests import analyze_k8s
    return analyze_k8s(tmp_path)["facts"]


def test_analyze_judge_graph_offline(no_network, tmp_path):
    from platformforge.graph import GraphBuilder
    from platformforge.models import Fact
    from platformforge.resources import data_path
    from platformforge.rules import RuleEngine, load_catalog
    facts = _facts(tmp_path)
    findings, _ = RuleEngine(
        load_catalog(data_path("rules", "catalog"))).evaluate(
        [Fact.from_dict(f) for f in facts])
    assert any(f.status == "violated" for f in findings)
    g = GraphBuilder().from_facts(facts).graph
    assert g.nodes


def test_index_and_pack_offline(no_network, tmp_path):
    from platformforge.tokensave.budget import Budget
    from platformforge.tokensave.index import SearchIndex
    from platformforge.tokensave.packs import ContextPackBuilder
    _facts(tmp_path)
    idx = SearchIndex(tmp_path / "i.db")
    idx.index_workspace(tmp_path)
    pack = ContextPackBuilder(idx, None).build(
        task="review deployment", budget=Budget(input_budget=2000))
    assert pack["est_input_tokens"] >= 0


def test_knowledge_and_rules_offline(no_network):
    from platformforge.knowledge.packs import PackRegistry
    from platformforge.knowledge.registry import SourceRegistry
    assert SourceRegistry.default().contract_check()["ok"]
    assert PackRegistry.default().contract_check()["ok"]


def test_no_network_imports_in_core():
    """§92 — the core ships no provider SDK / HTTP client imports."""
    import re
    from pathlib import Path
    pkg = Path(__file__).resolve().parents[1] / "platformforge"
    pat = re.compile(
        r"^\s*(import|from)\s+(boto3|botocore|requests|httpx|urllib3|"
        r"google\.cloud|azure)\b", re.MULTILINE)
    offenders = [str(f) for f in pkg.rglob("*.py")
                 if pat.search(f.read_text(encoding="utf-8"))]
    assert not offenders, offenders
