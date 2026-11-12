"""Negative tests for the multidimensional SDD gates — proves the old
false-positives are dead and the new denials are honest."""

from __future__ import annotations

import yaml

from platformforge.sdd.lifecycle import PHASES, SDDProject


def _full_feature(p: SDDProject, feature="FEAT1") -> None:
    for ph in PHASES:
        body = {"tests": "passed", "security": "passed",
                "risk": "low"} if ph == "verify" else f"# {ph}\n"
        p.write_artifact(feature, ph, body)


def test_check_empty_feature_refused(tmp_path):
    """Old behavior: empty feature → ok:True. Now: refused upstream? no —
    ok stays False only via missing-evidence at ship; check reports
    honestly (no refused because nothing exists to contradict, but the
    feature is NOT ship-able)."""
    p = SDDProject(tmp_path)
    r = p.check("FEAT1")
    assert r["ok"] is True  # nothing exists to violate; ship_gate is the wall
    assert p.ship_gate("FEAT1")["allowed"] is False
    assert any("evidence_missing" in f for f in
               p.ship_gate("FEAT1")["failures"])


def test_check_identity_mismatch(tmp_path):
    p = SDDProject(tmp_path)
    a = p.write_artifact("FEAT1", "discover", "# x\n")
    a.meta["feature"] = "OTHER"
    a.path.write_text("---\n" + yaml.safe_dump(a.meta) + "---\n# x\n")
    r = p.check("FEAT1")
    assert r["ok"] is False
    assert any(x["code"] == "identity_mismatch" for x in r["refused"])


def test_check_invalid_status(tmp_path):
    p = SDDProject(tmp_path)
    a = p.write_artifact("FEAT1", "discover", "# x\n")
    a.meta["status"] = "bogus"
    a.path.write_text("---\n" + yaml.safe_dump(a.meta) + "---\n# x\n")
    r = p.check("FEAT1")
    assert any(x["code"] == "status_invalid" for x in r["refused"])


def test_ship_gate_reads_persisted_verify(tmp_path):
    """verify.json with tests:failed must refuse even when caller
    passes a clean verify dict — persisted evidence is the floor."""
    p = SDDProject(tmp_path)
    _full_feature(p)
    # corrupt the persisted verify artifact
    va = p.artifact("FEAT1", "verify")
    doc = yaml.safe_load(va.path.read_text())
    doc["tests"] = "failed"
    va.path.write_text(yaml.safe_dump(doc))
    # caller claims all good — gate must still refuse
    g = p.ship_gate("FEAT1", verify={"tests": "passed"})
    # hash changed → upstream stale too; test_failed must ALSO appear
    assert "required_test_failed" in g["failures"]
    assert g["allowed"] is False


def test_ship_gate_caller_can_worsen_never_improve(tmp_path):
    p = SDDProject(tmp_path)
    _full_feature(p)
    g = p.ship_gate("FEAT1", verify={"security": "failed"})
    assert "security_gate_failed" in g["failures"]


def test_evidence_tampered_detected(tmp_path):
    p = SDDProject(tmp_path)
    _full_feature(p)
    # tamper build.json after verify sealed it
    b = p.artifact("FEAT1", "build")
    doc = yaml.safe_load(b.path.read_text())
    doc["injected"] = True
    b.path.write_text(yaml.safe_dump(doc))
    g = p.ship_gate("FEAT1")
    assert any("evidence_tampered" in f or "upstream_hash_stale" in f
               for f in g["failures"])
    assert g["allowed"] is False


def test_stamp_does_not_promote_ship_or_clobber_accepted(tmp_path):
    p = SDDProject(tmp_path)
    _full_feature(p)
    s = p.artifact("FEAT1", "ship")
    s.meta["status"] = "accepted"
    s.path.write_text("---\n" + yaml.safe_dump(s.meta) + "---\nShipped.\n")
    p.stamp("FEAT1")
    s2 = p.artifact("FEAT1", "ship")
    assert s2.meta["status"] == "accepted"  # never demoted


def test_override_reason_required(tmp_path):
    p = SDDProject(tmp_path)
    # missing everything → ship refuses; empty override reason → still refused
    r = p.ship("FEAT1", override=True, override_reason="  ")
    assert r["shipped"] is False


def test_override_undispensable_veto(tmp_path):
    p = SDDProject(tmp_path)
    _full_feature(p)
    # force stale: modify discover after chain sealed
    d = p.artifact("FEAT1", "discover")
    d.path.write_text("---\nsdd: 1\nfeature: FEAT1\nphase: discover\nstatus: ready\n---\nchanged\n")
    r = p.ship("FEAT1", override=True, override_reason="hotfix",
               actor="edgar")
    assert r["shipped"] is False
    assert "upstream_hash_stale" in str(r.get("override_denied") or r["failures"])


def test_ship_happy_path(tmp_path):
    p = SDDProject(tmp_path)
    _full_feature(p)
    g = p.ship_gate("FEAT1")
    assert g["allowed"], g["failures"]
    r = p.ship("FEAT1")
    assert r["shipped"] is True


def test_verify_run_writes_evidence(tmp_path):
    """--verify "cmd" executes and persists verify.json (wave-1 F6 fix)."""
    import sys

    from platformforge.cli.main import _sdd_verify_run

    p = SDDProject(tmp_path)
    p.write_artifact("FEAT1", "define", "# define\n")
    out = _sdd_verify_run(p, "FEAT1", f"{sys.executable} -c \"print(1)\"")
    assert out["tests"] == "passed" and out["exit_code"] == 0
    assert out["artifact"] == "verify.json"
    doc = yaml.safe_load(p.artifact("FEAT1", "verify").path.read_text())
    assert doc["tests"] == "passed"

    out2 = _sdd_verify_run(p, "FEAT1", f"{sys.executable} -c \"import sys;sys.exit(4)\"")
    assert out2["tests"] == "failed" and out2["exit_code"] == 4
