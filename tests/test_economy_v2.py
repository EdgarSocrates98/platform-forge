"""Cycle 2 Phase B — TokenSave v2, budget decisions, strategy, QPT."""
from __future__ import annotations

import tempfile
from pathlib import Path

from platformforge.economy import EconomyEngine
from platformforge.tokensave.budget import Budget
from platformforge.tokensave.index import SearchIndex
from platformforge.tokensave.ledger import LedgerEntry
from platformforge.tokensave.packs import ContextPackBuilder


def _ws(tmp: Path) -> SearchIndex:
    root = tmp / "ws"
    root.mkdir()
    (root / "main.tf").write_text('resource "aws_s3_bucket" "b" {}\n')
    (root / "deploy.yaml").write_text("kind: Deployment\nreplicas: 1\n")
    (root / "iam.json").write_text('{"Statement": []}\n')
    idx = SearchIndex(tmp / "idx.db")
    idx.index_workspace(root)
    return idx


def test_pack_items_have_reasons():
    """§25 — every included file explains why."""
    with tempfile.TemporaryDirectory() as td:
        idx = _ws(Path(td))
        pack = ContextPackBuilder(idx).build(
            "deploy review", changed_files=["deploy.yaml"])
        assert pack["relevant_files"]
        for f in pack["relevant_files"]:
            assert f["reasons"], f
            assert "score" in f and "class" in f


def test_essential_over_budget_refuses():
    """§27–28 — essential evidence over budget → refuse, never silent drop."""
    with tempfile.TemporaryDirectory() as td:
        idx = _ws(Path(td))
        facts = [{"fact_id": f"PF-X-{i}", "kind": "k", "tier": 3,
                  "attrs": {"big": "x" * 5000}} for i in range(3)]
        pack = ContextPackBuilder(idx).build(
            "t", budget=Budget(input_budget=10), facts=facts)
        assert pack["budget_decision"] == "refuse"
        assert pack["refusals"][0]["code"] == "PF-BUDGET-ESSENTIAL"
        assert pack["relevant_files"] == []


def test_graph_aware_ranking():
    """§22/§24 — graph neighborhood boosts matching paths."""
    with tempfile.TemporaryDirectory() as td:
        idx = _ws(Path(td))
        pack = ContextPackBuilder(idx).build(
            "audit", graph_neighborhood=[{"node": "workload/deploy", "depth": 1}])
        paths = {f["path"]: f for f in pack["relevant_files"]}
        assert "deploy.yaml" in paths
        assert any(r.startswith("graph-distance") for r in paths["deploy.yaml"]["reasons"])


def test_ledger_v2_fields(tmp_path):
    """§29 — v2 ledger records candidate/selected/essential splits."""
    e = LedgerEntry(operation="context.pack", context_requested=100,
                    context_candidate=80, context_selected=40,
                    context_delivered=40, essential_tokens=10,
                    optional_tokens=30)
    d = e.to_dict()
    for k in ("context_candidate", "context_selected", "essential_tokens",
              "optional_tokens", "reasoning_tokens", "cost_usd"):
        assert k in d


def test_strategy_deterministic_first():
    """§33 — deterministic tasks never escalate to a model."""
    eng = EconomyEngine(tempfile.mkdtemp())
    s = eng.strategy({"task_type": "lint", "question_kind": "lint"})
    assert s["strategy"] == "deterministic-only"
    s2 = eng.strategy({"task_type": "incident", "risk": "high",
                       "evidence_available": True})
    assert s2["strategy"] == "review-required"
    s3 = eng.strategy({"task_type": "analysis", "evidence_available": False})
    assert s3["strategy"] == "refuse"


def test_champion_challenger_shadow():
    """§36 — compare records shadow entries, never auto-enables."""
    eng = EconomyEngine(tempfile.mkdtemp())
    out = eng.compare({"task_type": "review", "complexity": "medium"})
    assert out["mode"] == "shadow"
    assert set(out["strategies"]) == {"single-specialist", "coordinated"}


def test_qpt_measures_recall():
    """§30–32 — QPT reports recall/precision/reduction + gate verdict."""
    from platformforge.economy.qpt import quality_per_token
    with tempfile.TemporaryDirectory() as td:
        idx = _ws(Path(td))
        facts = [{"fact_id": "PF-K8S-901", "kind": "k8s.workload", "tier": 3,
                  "source": "deploy.yaml", "location": "deploy.yaml",
                  "attrs": {"pod_spec": {"latest_tag": True}}},
                 {"fact_id": "PF-K8S-902", "kind": "k8s.workload", "tier": 3,
                  "source": "deploy.yaml", "location": "deploy.yaml",
                  "attrs": {"pod_spec": {"latest_tag": True}}}]
        rep = quality_per_token(facts_full=facts, findings_full=[],
                                index=idx, task="k8s deploy review",
                                budget=Budget(input_budget=50_000))
        assert "finding_recall" in rep and "token_reduction" in rep
        assert rep["quality_gate"] in ("pass", "fail")
