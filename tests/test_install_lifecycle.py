"""PORTABLE_INSTALL_LIFECYCLE — ``platformforge install`` forge/* surface.

Adapter over ``platformforge.distribution`` plan/apply/uninstall/upgrade +
vendored installkit: dry-run plans, approval refusal, managed apply,
health docs, drift/repair, reversible uninstall, and MCP handshake.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from platformforge.install import service


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    root = tmp_path / "my-project"
    root.mkdir()
    (root / ".git").mkdir()
    return root


# --- AC1: dry-run plans without writing ---------------------------------


def test_dry_run_plans_and_writes_nothing(project: Path) -> None:
    doc = service.install(scope="project", root=project, dry_run=True)
    assert doc["schema"] == "forge/InstallReceipt/v1"
    assert doc["status"] == "planned"
    assert doc["dry_run"] is True
    assert doc["planned_files"]
    assert not (project / ".platformforge").exists()


# --- AC2: writes require approval ---------------------------------------


def test_install_without_yes_is_refused(project: Path) -> None:
    with pytest.raises(service.InstallRefusal) as exc:
        service.install(scope="project", root=project, yes=False)
    assert exc.value.kind == "FORGE-INSTALL-PLAN-NOT-APPROVED"


def test_bad_profile_and_host_refused(project: Path) -> None:
    with pytest.raises(service.InstallRefusal) as exc:
        service.install(scope="project", root=project, profile="bogus",
                        yes=True)
    assert exc.value.kind == "FORGE-INSTALL-PROFILE-UNKNOWN"
    with pytest.raises(service.InstallRefusal) as exc:
        service.install(scope="project", root=project, host="bogus",
                        yes=True)
    assert exc.value.kind == "FORGE-INSTALL-HOST-UNKNOWN"


def test_project_scope_requires_repo(tmp_path: Path) -> None:
    plain = tmp_path / "not-a-repo"
    plain.mkdir()
    with pytest.raises(service.InstallRefusal) as exc:
        service.install(scope="project", root=plain, yes=True)
    assert exc.value.kind == "FORGE-INSTALL-NOT-A-REPO"


def test_workspace_scope_accepts_fresh_directory(tmp_path: Path) -> None:
    doc = service.install(scope="workspace", root=tmp_path, dry_run=True)
    assert doc["status"] == "planned"


# --- AC3: apply writes managed assets + receipt --------------------------


def test_install_apply_writes_managed_assets(project: Path) -> None:
    doc = service.install(scope="project", root=project, yes=True)
    assert doc["schema"] == "forge/InstallReceipt/v1"
    assert doc["status"] == "completed"
    rec = project / ".platformforge" / "install-receipt.json"
    assert rec.is_file()
    assert doc["managed_files"]
    assert (project / ".agents" / "skills" /
            "platformforge-core" / "SKILL.md").is_file()


def test_host_claude_scope(project: Path) -> None:
    doc = service.install(scope="project", root=project, host="claude",
                          yes=True)
    assert doc["status"] == "completed"
    assert (project / ".claude" / "skills" /
            "platformforge-core" / "SKILL.md").is_file()
    assert not (project / ".agents" / "skills").exists()


# --- AC4: status/doctor emit forge/InstallationHealth/v1 ------------------


def test_status_and_doctor_health_schema(project: Path) -> None:
    service.install(scope="project", root=project, yes=True)
    status = service.status(scope="project", root=project)
    assert status["schema"] == "forge/InstallationHealth/v1"
    assert status["status"] in ("healthy", "degraded", "unverified")
    doc = service.doctor(scope="project", root=project)
    assert doc["schema"] == "forge/InstallationHealth/v1"
    assert any(c["id"] == "mcp-handshake" for c in doc["checks"])


def test_status_on_uninstalled_is_unverified(project: Path) -> None:
    status = service.status(scope="project", root=project)
    assert status["status"] == "unverified"


def test_mcp_verify_check() -> None:
    check = service.mcp_verify()
    assert check["id"] == "mcp-handshake"
    assert check["status"] in ("PASS", "FAIL", "NOT_APPLICABLE", "BLOCKED")


# --- AC5: drift detection + repair ----------------------------------------


def test_repair_restores_missing_managed(project: Path) -> None:
    doc = service.install(scope="project", root=project, yes=True)
    managed = next(p for p in doc["managed_files"] if "skills/" in p)
    target = project / managed
    original = target.read_bytes()
    target.unlink()
    out = service.repair(scope="project", root=project)
    assert out["status"] == "completed"
    assert target.read_bytes() == original


def test_repair_preserves_user_modified(project: Path) -> None:
    doc = service.install(scope="project", root=project, yes=True)
    managed = next(p for p in doc["managed_files"] if "skills/" in p)
    target = project / managed
    target.write_text("user customized this mirror")
    out = service.repair(scope="project", root=project)
    assert out["status"] == "completed"
    assert target.read_text() == "user customized this mirror"
    assert managed in out["kept"]


def test_repair_dry_run_reports_drift(project: Path) -> None:
    doc = service.install(scope="project", root=project, yes=True)
    managed = project / doc["managed_files"][0]
    managed.write_text("drifted")
    out = service.repair(scope="project", root=project, dry_run=True)
    assert out["status"] == "planned"
    assert doc["managed_files"][0] in out["modified"]
    assert managed.read_text() == "drifted"


def test_repair_without_install_refused(project: Path) -> None:
    with pytest.raises(service.InstallRefusal) as exc:
        service.repair(scope="project", root=project)
    assert exc.value.kind == "FORGE-INSTALL-NOT-INSTALLED"


# --- AC6: uninstall is reversible and conservative ------------------------


def test_uninstall_removes_managed_preserves_modified(project: Path) -> None:
    doc = service.install(scope="project", root=project, yes=True)
    # Preserve a file outside .agents/skills so the mirror tree still prunes.
    victim_rel = next(p for p in doc["managed_files"]
                      if not p.startswith(".agents/skills"))
    victim = project / victim_rel
    victim.write_text("user content — keep")
    out = service.uninstall(scope="project", root=project)
    assert out["status"] == "completed"
    assert victim.is_file()  # modified → preserved
    assert victim_rel in out["kept"]
    assert not (project / ".platformforge" / "install-receipt.json").exists()
    assert not (project / ".agents" / "skills").exists()


def test_uninstall_on_pristine_root_is_noop(project: Path) -> None:
    out = service.uninstall(scope="project", root=project)
    assert out["status"] == "completed"
    assert not (project / ".platformforge").exists()


# --- AC7: CLI dispatch ----------------------------------------------------


def test_cli_dispatches_verbs(project: Path,
                              capsys: pytest.CaptureFixture[str]) -> None:
    from platformforge.cli.main import main

    rc = main(["install", "--repo", str(project), "--dry-run"])
    assert rc == 0
    capsys.readouterr()
    rc = main(["install", "status", "--repo", str(project)])
    out = capsys.readouterr().out
    assert '"forge/InstallationHealth/v1"' in out
    capsys.readouterr()
    rc = main(["install", "mcp-verify"])
    out = capsys.readouterr().out
    assert '"mcp-handshake"' in out
    assert rc in (0, 1)


def test_cli_apply_and_uninstall(project: Path) -> None:
    from platformforge.cli.main import main

    rc = main(["install", "--repo", str(project), "--yes"])
    assert rc == 0
    assert (project / ".platformforge" / "install-receipt.json").is_file()
    rc = main(["install", "uninstall", "--repo", str(project)])
    assert rc == 0
    assert not (project / ".platformforge" /
                "install-receipt.json").exists()


def test_hosts_none_e_csv():
    """GAP-003: `none` nunca vira `all`; csv subconjunto e validado."""
    import pytest

    from platformforge.install import service
    assert service._hosts("all")
    assert service._hosts("none") == []
    assert service._hosts("") == []
    assert len(service._hosts("claude,devin")) == 2
    with pytest.raises(service.InstallRefusal):
        service._hosts("nope")


# --- forge/context/v1 — workspace registry (install-2.0 ciclo 2) ----------


def test_install_escreve_forge_context(project: Path) -> None:
    import json

    from platformforge import _forgecontext as fctx

    out = service.install(scope="project", root=project, yes=True)
    assert out["status"] == "completed"
    check = next(c for c in out["checks"] if c["id"] == "context-registry")
    assert check["status"] == "PASS"

    ctx = project / ".forge" / "context"
    registry = json.loads((ctx / "registry.json").read_text(encoding="utf-8"))
    assert registry["schema"] == "forge/context-registry/v1"
    entry = next(
        e for e in registry["forges"] if e["forge_id"] == "platform-forge")
    assert entry["scope"] == "project"

    manifest = json.loads(
        (ctx / "capabilities" / "platform-forge.json").read_text(
            encoding="utf-8"))
    assert manifest["schema"] == "forge/context/v1"
    assert fctx.validate_manifest(manifest) == []
    assert manifest["skills"], "manifesto sem skills reais"
    assert manifest["agents"], "manifesto sem roster agents"
    assert manifest["integrity"]["files"]["forge.json"].startswith("sha256:")

    routing = (ctx / "ROUTING.md").read_text(encoding="utf-8")
    assert "platform-forge" in routing
    assert "platform-engineering" in routing


def test_install_context_idempotente_byte_a_byte(project: Path) -> None:
    service.install(scope="project", root=project, yes=True)
    ctx = project / ".forge" / "context"
    snap = {
        p.relative_to(ctx).as_posix(): p.read_bytes()
        for p in sorted(ctx.rglob("*"))
        if p.is_file()
    }
    service.install(scope="project", root=project, yes=True)
    depois = {
        p.relative_to(ctx).as_posix(): p.read_bytes()
        for p in sorted(ctx.rglob("*"))
        if p.is_file()
    }
    assert snap == depois


def test_uninstall_desregistra_so_o_proprio_forge(project: Path) -> None:
    import json

    from platformforge import _forgecontext as fctx

    service.install(scope="project", root=project, yes=True)
    estrangeiro = fctx.build_manifest(
        forge_id="forge-alheia",
        name="Forge Alheia",
        version="1.0.0",
        cli="forge-alheia",
        package="forge_alheia",
        distribution="forge-alheia",
        python_spec=">=3.10",
        scope="project",
        domains=("dominio-alheio",),
        skills=("skill-alheia",),
    )
    fctx.register_forge(project, estrangeiro, owner="forge-alheia")

    un = service.uninstall(scope="project", root=project)
    assert un["status"] == "completed"

    ctx = project / ".forge" / "context"
    registry = json.loads((ctx / "registry.json").read_text(encoding="utf-8"))
    assert {e["forge_id"] for e in registry["forges"]} == {"forge-alheia"}
    assert not (ctx / "capabilities" / "platform-forge.json").exists()
    assert (ctx / "capabilities" / "forge-alheia.json").exists()
