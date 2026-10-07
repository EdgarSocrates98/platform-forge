"""Wave K — §117–129: eval variants/coverage, property tests (graph +
security), lab profiles, store GC."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CASES = REPO / "evals" / "cases"

SECRET = "AKIAIOSFODNN7EXAMPLE"  # well-known AWS docs example key
SECRET_BLOB = f"aws_access_key_id = {SECRET}\npassword: hunter2-hunter2"


# ── §125 graph property tests ──────────────────────────────


def _facts():
    return [
        {"fact_id": "F-1", "kind": "k8s.workload", "source": "a.yaml",
         "location": "a.yaml::prod/api", "tier": 3,
         "attrs": {"graph": {
             "nodes": [{"kind": "workload", "label": "prod/api"}],
             "edges": [{"src_kind": "workload", "src": "prod/api",
                        "dst_kind": "namespace", "dst": "prod",
                        "kind": "contained_by"}]}}},
        {"fact_id": "F-2", "kind": "k8s.workload", "source": "b.yaml",
         "location": "b.yaml::prod/db", "tier": 3,
         "attrs": {"graph": {
             "nodes": [{"kind": "workload", "label": "prod/db"}],
             "edges": [{"src_kind": "workload", "src": "prod/api",
                        "dst_kind": "workload", "dst": "prod/db",
                        "kind": "depends_on"}]}}},
        # tier 6 = inferred — must never produce an observed edge
        {"fact_id": "F-3", "kind": "k8s.workload", "source": "guess",
         "location": "guess", "tier": 6,
         "attrs": {"graph": {
             "edges": [{"src_kind": "workload", "src": "prod/api",
                        "dst_kind": "secret", "dst": "prod/x",
                        "kind": "uses_secret"}]}}},
        # tier 2 = plan — planned, never observed
        {"fact_id": "F-4", "kind": "tf.plan", "source": "plan.json",
         "location": "plan.json", "tier": 2,
         "attrs": {"graph": {
             "nodes": [{"kind": "bucket", "label": "logs"}],
             "edges": [{"src_kind": "workload", "src": "prod/api",
                        "dst_kind": "bucket", "dst": "logs",
                        "kind": "writes"}]}}},
    ]


def test_graph_roundtrip_deterministic():
    from platformforge.graph import GraphBuilder
    from platformforge.graph.model import Graph
    facts = _facts()
    g1 = GraphBuilder().from_facts(facts).graph
    g2 = GraphBuilder().from_facts(list(reversed(facts))).graph
    assert g1.graph_hash == g2.graph_hash  # order-independent
    rt = Graph.from_dict(json.loads(g1.to_json()))
    assert rt.graph_hash == g1.graph_hash
    assert rt.to_json() == g1.to_json()


def test_graph_edges_carry_fact_ids():
    from platformforge.graph import GraphBuilder
    g = GraphBuilder().from_facts(_facts()).graph
    fact_ids = {"F-1", "F-2", "F-3", "F-4"}
    assert g.edges
    for e in g.edges.values():
        assert e.source_fact_ids, f"edge {e.eid} lacks provenance"
        assert set(e.source_fact_ids) <= fact_ids


def test_graph_no_observed_from_inferred():
    from platformforge.graph import GraphBuilder
    g = GraphBuilder().from_facts(_facts()).graph
    inferred_only = [e for e in g.edges.values()
                     if e.provenance == "observed"
                     and set(e.source_fact_ids) == {"F-3"}]
    assert not inferred_only
    e = next(e for e in g.edges.values() if e.kind == "uses_secret")
    assert e.provenance == "inferred"


def test_graph_planned_never_observed():
    from platformforge.graph import GraphBuilder
    facts = [_facts()[3]]  # only the tier-2 plan fact
    g = GraphBuilder().from_facts(facts).graph
    e = next(iter(g.edges.values()))
    assert e.provenance == "planned"
    node = g.nodes["bucket/logs"]
    assert node.attrs["state"] == "planned"


def test_graph_diff_deterministic():
    from platformforge.graph import GraphBuilder
    from platformforge.graph.diff import diff
    before = GraphBuilder().from_facts(_facts()[:1]).graph
    after = GraphBuilder().from_facts(_facts()).graph
    d1, d2 = diff(before, after), diff(before, after)
    assert json.dumps(d1, sort_keys=True) == json.dumps(d2, sort_keys=True)
    assert d1["hash_after"] == after.graph_hash
    assert d1["nodes_added"] or d1["edges_added"]


def test_graph_blast_deterministic_and_classed():
    from platformforge.graph import GraphBuilder
    from platformforge.graph.query import blast_radius
    g = GraphBuilder().from_facts(_facts()).graph
    b1 = blast_radius(g, "workload/prod-api")
    b2 = blast_radius(g, "workload/prod-api")
    assert json.dumps(b1, sort_keys=True) == json.dumps(b2, sort_keys=True)
    assert "by_class" in b1 or "nodes" in b1


def test_graph_vocab_enforced():
    from platformforge.graph import GraphBuilder
    with pytest.raises(ValueError):
        GraphBuilder().add_node("bogus-kind", "x")
    with pytest.raises(ValueError):
        GraphBuilder().add_edge("workload", "a", "secret", "b",
                                "not-an-edge-kind")


# ── §126 security property tests ───────────────────────────


def test_scan_secrets_never_emits_values(tmp_path):
    from platformforge.security import scan_secrets
    f = tmp_path / "creds.txt"
    f.write_text(SECRET_BLOB)
    out = scan_secrets(tmp_path)
    blob = json.dumps(out)
    assert SECRET not in blob and "hunter2-hunter2" not in blob
    assert out["counts"]["files_with_hits"] == 1


def test_caveman_output_never_contains_secret():
    from platformforge.caveman import compress
    for mode in ("off", "lite", "full", "auto"):
        out, receipt = compress(
            f"deploy failed. {SECRET_BLOB} rolled back.", mode=mode)
        assert SECRET not in out
        assert "hunter2-hunter2" not in out
        assert "redaction" in receipt.extra


def test_mcp_response_never_contains_secret(tmp_path):
    from platformforge.mcp.server import handle
    f = tmp_path / "leak.tf"
    f.write_text(f'resource "x" "y" {{ password = "{SECRET}" }}')
    resp = handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                   "params": {"name": "platformforge_analyze",
                              "arguments": {"domain": "iac",
                                            "path": str(tmp_path)}}},
                  repo=str(tmp_path))
    assert resp is not None
    # the tool must have actually analyzed (not errored before dispatch)
    msg = json.loads(resp) if isinstance(resp, str) else resp
    content = msg["result"]["content"][0]["text"]
    out = json.loads(content)
    assert "error" not in out and "refusal" not in out
    assert SECRET not in content
    assert "REDACTED" in content  # boundary redaction really ran


def test_mcp_artifact_store_never_persists_secret(tmp_path):
    """Oversize MCP results are stored redacted — rtk expand must not
    hand back raw secrets either (defense in depth on read)."""
    from platformforge.core.store import ArtifactStore
    from platformforge.mcp.tools import _bound
    from platformforge.rtk.compact import expand
    blob = {"big": "x" * 60_000, "leaked_key": SECRET,
            "leaked_pw": "hunter2-hunter2"}
    out = _bound(blob, type("C", (), {"max_bytes": 1000})(),
                 repo=str(tmp_path))
    assert out["bounded"] and SECRET not in json.dumps(out)
    sha = out["artifact_ref"].removeprefix("artifact://sha256/")
    stored = ArtifactStore(tmp_path).get_text(sha)
    assert stored is not None and SECRET not in stored
    exp = expand(ArtifactStore(tmp_path), out["artifact_ref"])
    assert SECRET not in json.dumps(exp)


def test_context_pack_bodies_redacted(tmp_path):
    from platformforge.tokensave.index import SearchIndex
    (tmp_path / "c.tf").write_text(
        f'resource "aws_db" "x" {{ password = "{SECRET}" }}\n')
    idx = SearchIndex(tmp_path / "i.db")
    idx.index_workspace(tmp_path)
    hits = idx.search(SECRET) if hasattr(idx, "search") else []
    blob = json.dumps(hits, default=str)
    assert SECRET not in blob


def test_artifact_refs_are_pointers(tmp_path):
    """artifact:// refs carry hashes — the raw payload stays in store."""
    from platformforge.core.store import ArtifactStore
    from platformforge.rtk import compact_output
    store = ArtifactStore(tmp_path)
    res = compact_output("kubectl", SECRET_BLOB + "\nx" * 4000,
                         store=store)
    d = res.to_dict()
    blob = json.dumps(d)
    assert "artifact://sha256/" in blob
    # compacted view must not inline a secret
    assert SECRET not in blob


# ── §118/§119 lab profiles ─────────────────────────────────


def test_lab_profile_guard(tmp_path, monkeypatch):
    from platformforge.lab import runner
    d = tmp_path / "cloudy"
    d.mkdir()
    (d / "expected.yaml").write_text(
        "profile: cloud\nanalyzers: []\nviolated_rules: []\n")
    monkeypatch.setattr(runner, "SCENARIOS_DIR", tmp_path)
    out = runner.run("cloudy")
    assert out["refusal"] == "platform.lab.profile_guard"
    out2 = runner.run("cloudy", allow_profile=True)
    assert out2["refusal"] == "platform.lab.safety_contract"
    assert "credentials" in out2["missing"]


def test_store_gc_protects_referenced(tmp_path):
    from platformforge.core.store import ArtifactStore
    store = ArtifactStore(tmp_path)
    keep = store.put_text("pinned")
    drop = store.put_text("stale")
    # age the stale blob past retention
    import os
    import time
    old = time.time() - 40 * 86400
    p = store._path(drop)
    os.utime(p, (old, old))
    meta = p.with_suffix(".meta.json")
    m = json.loads(meta.read_text())
    m["stored_at"] = old
    meta.write_text(json.dumps(m))
    out = store.gc(keep_days=30, referenced={keep})
    assert out["candidates"] == 1 and out["stale"][0]["sha256"] == drop
    assert store.has(drop) and store.has(keep)  # dry-run touched nothing
    out2 = store.gc(keep_days=30, referenced={keep}, dry_run=False)
    assert out2["removed"] == 1
    assert not store.has(drop) and store.has(keep)


# ── §122/§127 eval coverage + precision ────────────────────


def test_rule_coverage_report():
    from platformforge.evals.coverage import rule_coverage
    out = rule_coverage(CASES)
    rows = {r["rule_id"]: r for r in out["coverage"]}
    assert rows["PF-K8S-002"]["positive"] and rows["PF-K8S-002"]["negative"]
    assert rows["PF-K8S-002"]["boundary"]
    assert rows["PF-K8S-030"]["version"] or rows["PF-K8S-031"]["version"]
    assert out["counts"]["rules"] > 0


def test_precision_report_measured():
    from platformforge.evals.coverage import precision_report
    out = precision_report(CASES)
    assert out["counts"]["negative_checks"] > 0
    assert out["aggregate_precision"] is not None
    for r in out["precision"]:
        assert 0.0 <= r["precision"] <= 1.0


def test_eval_new_variants_pass():
    from platformforge.evals.runner import run_all
    out = run_all(CASES)
    by_id = {r["id"]: r for r in out["results"]}
    for cid in ("k8s-dep-api-v129", "k8s-dep-api-v120",
                "k8s-dep-api-unknown", "k8s-beta-api",
                "k8s-limits-boundary", "knowledge-registry"):
        assert by_id[cid]["verdict"] == "pass", by_id[cid]
    assert out["counts"]["fail"] == 0
