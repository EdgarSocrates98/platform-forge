"""Freeze machinery — manifest is generated (not stale prose),
snapshots detect drift, FeatureException enforces §6."""
import json

from platformforge.freeze import (
    build_manifest,
    build_snapshots,
    check_snapshots,
    exception_errors,
    write_snapshots,
)


def test_manifest_from_live_registries():
    m = build_manifest()
    assert m["schema"] == "platformforge/freeze-manifest/v1"
    assert m["agent_contracts"]["count"] == 41
    assert m["mcp_surfaces"] and "freeze" in m["cli_surfaces"]
    # honest labeling — nothing claims production validation
    assert m["production_unvalidated_claims"]


def test_snapshot_roundtrip(tmp_path):
    write_snapshots(repo=".", out=tmp_path)
    r = check_snapshots(repo=".", snap_dir=tmp_path)
    assert r["verdict"] == "pass", r["breaking"]


def test_snapshot_detects_breaking_drift(tmp_path):
    write_snapshots(repo=".", out=tmp_path)
    f = tmp_path / "schemas.json"
    d = json.loads(f.read_text())
    d["entries"]["fact.schema.json"] = "0" * 64  # simulate contract change
    f.write_text(json.dumps(d))
    r = check_snapshots(repo=".", snap_dir=tmp_path)
    assert r["verdict"] == "fail"
    assert any("changed schemas:fact.schema.json" in b for b in r["breaking"])


def test_knowledge_drift_is_allowlisted(tmp_path):
    write_snapshots(repo=".", out=tmp_path)
    f = tmp_path / "knowledge.json"
    d = json.loads(f.read_text())
    k = next(iter(d["entries"]))
    d["entries"][k] = "0" * 64
    f.write_text(json.dumps(d))
    r = check_snapshots(repo=".", snap_dir=tmp_path)
    assert r["verdict"] == "pass" and r["allowed"]


def test_exception_contract():
    good = {"id": "FE-1", "requested_capability": "x", "reason": "r",
            "real_world_blocker": "case-42",
            "existing_capability_insufficient": "judge returned unresolved",
            "alternatives_considered": ["a"], "architectural_impact": "small",
            "schema_impact": "none", "agent_impact": "none",
            "operations_impact": "none", "decision": "approved",
            "evidence": [".platformforge/cases/42/case.yaml"]}
    assert exception_errors(good) == []
    # approval without a real-world blocker is refused (§6, §210)
    bad = {**good, "real_world_blocker": ""}
    assert any("real_world_blocker" in e for e in exception_errors(bad))
    # missing required fields
    assert exception_errors({"id": "x"})
    # bad decision value
    assert exception_errors({**good, "decision": "maybe"})


def test_snapshots_cover_families():
    s = build_snapshots()
    for fam in ("schemas", "cli", "mcp", "capabilities", "agents"):
        assert s.get(fam), fam
    assert len(s["agents"]) == 41
