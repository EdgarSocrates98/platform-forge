"""Gap-closure gates: risk engine (§130-131), sandbox (§86),
multi-repo workspace (§126), explain/recommend."""

from pathlib import Path

from platformforge.cli.main import _member_dirs
from platformforge.risk.engine import assess_change, criticality
from platformforge.risk.signals import signals_from_graph
from platformforge.sandbox import compare_runs, sandbox_analyze


def test_risk_levels_decompose():
    low = assess_change({"reversibility": True, "test_coverage": True})
    assert low["level"] == "low"
    high = assess_change({"production": True, "identity_impact": True,
                          "security_impact": True, "criticality": "critical",
                          "blast_radius": 3})
    assert high["level"] in ("high", "critical")
    assert high["decomposition"]["production"]["score"] == 3
    # unresolved signals are named, never assumed
    assert "network_exposure" in high["unresolved"]


def test_criticality_declared_only():
    assert criticality({"tier": "tier0"}) == "critical"
    assert criticality({"criticality": "high"}) == "high"
    assert criticality({"type": "aws_db_instance"}) == "unresolved"  # not inferred


def test_risk_from_graph(tmp_path):
    from platformforge.graph import GraphBuilder, blast_radius
    b = GraphBuilder()
    b.add_node("workload", "prod/payments", attrs={"env": "prod",
                                                 "tier": "tier1"})
    b.add_node("database", "db-prod")
    b.add_edge("workload", "prod/payments", "database", "db-prod",
               "depends_on")
    # blast originates at the database — the workload is downstream
    blast = blast_radius(b.graph, "database/db-prod")
    sig = signals_from_graph(b.graph, ["database/db-prod"], blast)
    assert sig["production"] is True
    assert sig["data_persistence"] is True
    assert sig["criticality"] == 3


def test_sandbox_never_touches_original(tmp_path):
    (tmp_path / "deploy.yaml").write_text(
        "apiVersion: apps/v1\nkind: Deployment\nmetadata: {name: x}\n")
    sentinel = (tmp_path / "deploy.yaml").read_text()
    out = sandbox_analyze(
        tmp_path, files={"extra.tf": 'resource "aws_s3_bucket" "b" {}\n'})
    assert (tmp_path / "deploy.yaml").read_text() == sentinel
    assert not (tmp_path / "extra.tf").exists()  # only in sandbox copy
    assert out["delta"]["fact_kinds_added"].get("iac.resource") == 1
    assert out["before"]["facts"] and out["after"]["facts"]


def test_compare_runs():
    b = {"facts": [{"kind": "a", "fact_id": "PF-A-1"}]}
    a = {"facts": [{"kind": "a", "fact_id": "PF-A-1"},
                   {"kind": "b", "fact_id": "PF-A-2"}]}
    d = compare_runs(b, a)
    assert d["fact_kinds_added"] == {"b": 1} and d["facts_added"] == 1


def test_workspace_members(tmp_path):
    for m in ("app", "infra"):
        (tmp_path / m).mkdir()
    (tmp_path / "workspace.yaml").write_text(
        "members:\n  - {name: app, path: app, role: application}\n"
        "  - {name: infra, path: infra, role: infra}\n")
    members = _member_dirs(tmp_path)
    assert {n for n, _ in members} == {"app", "infra"}
    # pointing at a member dir resolves UP to the workspace — §126
    assert {n for n, _ in _member_dirs(tmp_path / "app")} == {"app", "infra"}
    # a dir outside any workspace stays single-member
    import tempfile
    with tempfile.TemporaryDirectory() as bare_dir:
        bare = Path(bare_dir)
        assert _member_dirs(bare) == [("", bare)]
