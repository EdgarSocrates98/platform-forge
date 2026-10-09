"""Cycle 2 Phase A — truth hardening tests (§4–§11, §16–§18, §108–§111)."""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from platformforge.graph.build import GraphBuilder, _tier_provenance
from platformforge.rules.engine import catalog_provenance_report


def test_t2_plan_is_planned_not_observed():
    """§4 — generated plans are `planned`, never `observed`."""
    assert _tier_provenance(0) == "observed"
    assert _tier_provenance(1) == "observed"
    assert _tier_provenance(2) == "planned"
    assert _tier_provenance(3) == "declared"
    assert _tier_provenance(6) == "inferred"


def test_node_state_resolution():
    """§5 — observed beats planned beats desired on a shared node."""
    facts = [
        {"fact_id": "PF-X-1", "kind": "iac.plan_resource", "tier": 2,
         "attrs": {"graph": {"nodes": [{"kind": "terraform_resource",
                                        "label": "aws_s3_bucket.b"}]}}},
        {"fact_id": "PF-X-2", "kind": "iac.state_resource", "tier": 1,
         "attrs": {"graph": {"nodes": [{"kind": "terraform_resource",
                                        "label": "aws_s3_bucket.b"}]}}},
    ]
    g = GraphBuilder().from_facts(facts).graph
    assert g.nodes["terraform_resource/aws_s3_bucket.b"].attrs["state"] == "observed"
    g2 = GraphBuilder().from_facts(facts[:1]).graph
    assert g2.nodes["terraform_resource/aws_s3_bucket.b"].attrs["state"] == "planned"


def test_all_rules_have_sources():
    """§9–§10 — 100% of executable rules name a dated source."""
    rep = catalog_provenance_report("rules/catalog")
    assert rep["missing_sources"] == []
    assert rep["coverage"] == 1.0


def test_index_never_stores_raw_secret():
    """§17 — TokenSave index stores redacted bodies + a receipt."""
    from platformforge.tokensave.index import SearchIndex
    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "ws"
        root.mkdir()
        (root / "config.py").write_text(
            'AWS_KEY = "AKIAIOSFODNN7EXAMPLE"\npassword="hunter2secret"\n')
        idx = SearchIndex(Path(td) / "idx.db")
        stats = idx.index_workspace(root)
        assert "redactions" in stats and "config.py" in stats["redactions"]
        body = idx.read("config.py")
        assert "AKIAIOSFODNN7EXAMPLE" not in body
        assert "REDACTED" in body


def test_detail_level_bounds_output(capsys):
    """§108 — summary/normal bound lists; full doesn't."""
    from platformforge.cli.main import _emit
    big = {"items": list(range(200)), "counts": {"n": 200}}
    a = argparse.Namespace(output=None, json=True, strict=False,
                           detail_level="normal", offline=False)
    _emit(big, a)
    out = json.loads(capsys.readouterr().out)
    assert len(out["items"]) == 51  # 50 + truncation marker
    a.detail_level = "full"
    _emit(big, a)
    out = json.loads(capsys.readouterr().out)
    assert len(out["items"]) == 200


def test_strict_exit_code_on_unresolved(capsys):
    """§110 — --strict turns unresolved payload into exit 2."""
    from platformforge.cli.main import _emit
    a = argparse.Namespace(output=None, json=True, strict=True,
                           detail_level="full", offline=False)
    assert _emit({"unresolved": ["x"]}, a) == 2
    assert _emit({"ok": True}, a) == 0
    capsys.readouterr()


def test_snapshot_envelope(tmp_path):
    """§6 — snapshot carries the full envelope."""
    from platformforge.graph import persist
    g = GraphBuilder().from_facts(
        [{"fact_id": "PF-X-1", "kind": "k", "tier": 3,
          "attrs": {"graph": {"nodes": [{"kind": "service", "label": "s"}]}}}]
    ).graph
    persist.save(g, tmp_path, source="facts.json", source_type="planned",
                 environment="prod")
    snaps = persist.snapshots(tmp_path)
    assert len(snaps) == 1
    meta = snaps[0]
    for k in persist.SNAPSHOT_FIELDS:
        assert k in meta
    assert meta["source_type"] == "planned"
    assert meta["environment"] == "prod"
    assert meta["graph_hash"] == g.graph_hash


def test_semantic_diff_cites_facts():
    """§7 — semantic categories cite fact_ids."""
    from platformforge.graph.diff import diff
    b = GraphBuilder().from_facts(
        [{"fact_id": "PF-B-1", "kind": "k", "tier": 3,
          "attrs": {"graph": {"nodes": [{"kind": "workload", "label": "w",
                                         "attrs": {"replicas": 1}}]}}}]).graph
    a = GraphBuilder().from_facts(
        [{"fact_id": "PF-A-1", "kind": "k", "tier": 3,
          "attrs": {"graph": {"nodes": [{"kind": "workload", "label": "w",
                                         "attrs": {"replicas": 3}}]}}}]).graph
    d = diff(b, a)
    assert d["semantic"]["ha"]["changed"] is True
    assert set(d["semantic"]["ha"]["fact_ids"]) == {"PF-A-1", "PF-B-1"}
