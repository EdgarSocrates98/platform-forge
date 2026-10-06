"""Phase 3 gate: SDD lifecycle, hash cascade, ship gates."""

from platformforge.sdd import SDDProject


def _drive(proj: SDDProject, feature: str):
    proj.write_artifact(feature, "discover", "# discovery\n")
    proj.write_artifact(feature, "define", "# define\n")
    proj.write_artifact(feature, "design", "# design\n")
    proj.write_artifact(feature, "contract", "# contract\n")
    proj.write_artifact(feature, "plan", "# plan\n")
    proj.write_artifact(feature, "build", {"tests": "passed"})
    proj.write_artifact(feature, "review", "# reviewed\n")
    proj.write_artifact(feature, "verify", {"tests": "passed"})


def test_sdd_lifecycle_and_upstream_hash(tmp_path):
    proj = SDDProject(tmp_path)
    _drive(proj, "FEAT")
    st = proj.status("FEAT")
    assert not st["stale"]
    design = proj.artifact("FEAT", "design")
    plan = proj.artifact("FEAT", "plan")
    assert plan.upstream["path"] == "contract.md"
    assert plan.upstream["sha256"]


def test_hash_cascade_marks_downstream_stale(tmp_path):
    proj = SDDProject(tmp_path)
    _drive(proj, "FEAT")
    proj.write_artifact("FEAT", "design", "# design v2 — changed\n")
    st = proj.status("FEAT")
    assert st["stale"] == ["build", "plan", "review", "ship", "verify", "learn"]\
        or set(st["stale"]) >= {"plan", "build", "review", "verify"}
    gate = proj.ship_gate("FEAT", verify={"tests": "passed"})
    assert not gate["allowed"] and "upstream_hash_stale" in gate["failures"][0]


def test_stamp_reseals(tmp_path):
    proj = SDDProject(tmp_path)
    _drive(proj, "FEAT")
    proj.write_artifact("FEAT", "design", "# design v2\n")
    assert proj.check("FEAT")["stale"]
    proj.stamp("FEAT")
    assert proj.check("FEAT")["ok"]


def test_ship_gate_refuses_missing_and_critical(tmp_path):
    proj = SDDProject(tmp_path)
    _drive(proj, "FEAT")
    out = proj.ship("FEAT", verify={"tests": "passed"})
    assert out["shipped"] is True
    proj2 = SDDProject(tmp_path)
    _drive(proj2, "FEAT2")
    out2 = proj2.ship("FEAT2", verify={"tests": "failed"})
    assert out2["shipped"] is False
    assert any("required_test_failed" in f for f in out2["failures"])
    out3 = proj2.ship(
        "FEAT2", verify={"tests": "passed"},
        findings=[{"severity": "critical", "status": "violated"}])
    assert out3["shipped"] is False
    assert "critical_finding_unresolved" in out3["failures"]


def test_ship_override_emits_receipt(tmp_path):
    proj = SDDProject(tmp_path)
    _drive(proj, "FEAT")
    out = proj.ship("FEAT", verify={"tests": "failed"}, override=True,
                    override_reason="mitigation deployed")
    assert out["shipped"] is True and out["override"] is True
    ship_art = proj.artifact("FEAT", "ship")
    assert ship_art.meta["override_receipt"]["reason"] == "mitigation deployed"
