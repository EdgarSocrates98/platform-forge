"""Phase G — pf-* executors: one job, structured output, no dispatch."""

from __future__ import annotations

from platformforge.agents.executors import (
    EXECUTORS,
    pf_extract,
    pf_graph_build,
    pf_inventory,
    pf_judge,
    pf_reconcile,
    pf_simulate,
    pf_synthesize,
    pf_verify,
)
from platformforge.agents.roster import AGENTS

TF = 'resource "aws_s3_bucket" "b" { bucket = "x" }\n'


def test_eight_executors_in_roster():
    for name in EXECUTORS:
        a = AGENTS.get(name)
        assert a is not None and a.role == "executor", name
        assert a.access == "read-only"
        assert not a.delegates_to, f"{name} must not dispatch (§66)"
        assert a.contract_errors() == []


def test_pf_inventory_and_extract(tmp_path):
    (tmp_path / "main.tf").write_text(TF)
    inv = pf_inventory(tmp_path)
    assert "iac" in inv["domains"]
    assert inv["artifact_count"] >= 1
    ext = pf_extract(tmp_path)
    assert ext["count"] >= 1
    assert all(fid.startswith("PF-") for fid in ext["fact_ids"])


def test_pf_judge_and_graph(tmp_path):
    (tmp_path / "main.tf").write_text(TF)
    facts = pf_extract(tmp_path)["facts"]
    judged = pf_judge(facts, [])
    assert "findings" in judged and "skipped" in judged
    # graph contribution via attrs.graph — make one synthetic fact
    contrib = dict(facts[0])
    contrib["attrs"] = dict(contrib.get("attrs") or {})
    contrib["attrs"]["graph"] = {
        "nodes": [{"kind": "service", "label": "a"},
                  {"kind": "service", "label": "b"}],
        "edges": [{"src_kind": "service", "src": "a",
                   "dst_kind": "service", "dst": "b",
                   "kind": "depends_on"}]}
    g = pf_graph_build([contrib])
    assert g["nodes"] == 2 and g["edges"] == 1
    assert g["unprovenanced_edges"] == []


def test_pf_reconcile_keeps_states_distinct():
    out = pf_reconcile(desired={"a": 1, "b": 1},
                       planned={"a": 1},
                       observed={"a": 1, "c": 1})
    assert out["planned_not_observed"] == []  # a is observed
    assert out["observed_unplanned"] == ["c"]
    assert out["desired_only"] == ["b"]
    assert out["converged"] == ["a"]


def test_pf_simulate_delta_only():
    out = pf_simulate(
        observed_graph={"nodes": {"a": {}}, "edges": {}},
        planned_graph={"nodes": {"a": {}, "b": {}},
                       "edges": {"a->b": {}}},
        plan_hash="h")
    assert out["expected_delta"]["adds"]["resources"] == ["b"]
    assert out["expected_delta"]["adds"]["dependencies"] == ["a->b"]
    assert out["expected_delta"]["removes"]["resources"] == []


def test_pf_synthesize_references_only():
    findings = [{"status": "confirmed", "evidence": ["F-1"],
                 "claim": "ok"},
                {"status": "unresolved", "evidence": [],
                 "claim": "gap"}]
    out = pf_synthesize(findings=findings,
                        graph={"nodes": {"x": {}}},
                        reviews=[{"verdict": "pass"}])
    assert out["evidence"] == ["F-1"]
    assert out["unresolved"] == ["gap"]
    assert out["graph_nodes"] == 1


def test_pf_verify_hash_and_fields():
    doc = {"receipt_id": "R-1", "x": 1}
    ok = pf_verify(doc=doc)
    assert ok["ok"]
    bad = pf_verify(doc={"receipt_id": "R-1"}, expected_hash="sha256:z")
    assert not bad["ok"] and any("hash" in p for p in bad["problems"])
    missing = pf_verify(doc={"x": 1})
    assert any("receipt_id" in p for p in missing["problems"])
