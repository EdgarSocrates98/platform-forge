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


# --- consumer docs + .mcp.json — install-2.0 ciclo 3 (lf-0036) ----------


def test_install_escreve_consumer_docs_e_mcp(project: Path) -> None:
    import json

    out = service.install(scope="project", root=project, yes=True)
    assert out["status"] == "completed"
    ids = {c["id"]: c["status"] for c in out["checks"]}
    assert ids.get("consumer-docs") == "PASS"
    assert ids.get("mcp-json") == "PASS"

    agents = (project / "AGENTS.md").read_text(encoding="utf-8")
    claude = (project / "CLAUDE.md").read_text(encoding="utf-8")
    proto = (project / "AGENT_PROTOCOL.md").read_text(encoding="utf-8")
    assert "<!-- forge:ecosystem:begin -->" in agents
    assert "<!-- forge:platform-forge:begin -->" in agents
    assert "@AGENTS.md" in claude
    assert proto.startswith("<!-- forge:agent-protocol:v1 -->")
    for sec in (
        "1. Discovery", "2. Classification", "3. Routing",
        "4. Context Retrieval", "5. Planning", "6. Execution",
        "7. Evaluation", "8. Verification", "9. Reporting",
    ):
        assert sec in proto

    mcp = json.loads((project / ".mcp.json").read_text(encoding="utf-8"))
    assert mcp["mcpServers"]["platformforge"]["command"] == "platformforge-mcp"
    assert "platform-forge" in mcp["_forge_managed"]


def test_install_docs_idempotente_byte_a_byte(project: Path) -> None:
    service.install(scope="project", root=project, yes=True)
    nomes = ("AGENTS.md", "CLAUDE.md", "AGENT_PROTOCOL.md", ".mcp.json")
    snap = {n: (project / n).read_bytes() for n in nomes}
    service.install(scope="project", root=project, yes=True)
    assert {n: (project / n).read_bytes() for n in nomes} == snap


def test_install_preserva_conteudo_do_usuario(project: Path) -> None:
    import json

    (project / "AGENTS.md").write_text("# minhas regras\nuser text\n",
                                       encoding="utf-8")
    (project / ".mcp.json").write_text(json.dumps(
        {"mcpServers": {"other": {"command": "x"}}, "own": True}))
    service.install(scope="project", root=project, yes=True)
    agents = (project / "AGENTS.md").read_text(encoding="utf-8")
    assert agents.startswith("# minhas regras\nuser text\n")
    mcp = json.loads((project / ".mcp.json").read_text(encoding="utf-8"))
    assert mcp["mcpServers"]["other"] == {"command": "x"}
    assert mcp["own"] is True


def test_uninstall_seletivo_docs_entre_forges(project: Path) -> None:
    import json

    from platformforge import _forgecontext as fctx

    service.install(scope="project", root=project, yes=True)
    alheio = fctx.build_manifest(
        forge_id="forge-alheia", name="Forge Alheia", version="1.0.0",
        cli="forge-alheia", package="forge_alheia",
        distribution="forge-alheia", python_spec=">=3.10",
        scope="project", domains=("dominio-alheio",),
        skills=("skill-alheia",),
    )
    fctx.register_forge(project, alheio, owner="forge-alheia")
    fctx.install_docs(project, alheio, owner="forge-alheia")

    service.uninstall(scope="project", root=project)
    agents = (project / "AGENTS.md").read_text(encoding="utf-8")
    assert "forge:platform-forge" not in agents
    assert "forge:forge-alheia:begin" in agents
    proto = (project / "AGENT_PROTOCOL.md").read_text(encoding="utf-8")
    assert "forge:forge-alheia" in proto and "platform-forge" not in proto
    if (project / ".mcp.json").exists():
        mcp = json.loads((project / ".mcp.json").read_text(encoding="utf-8"))
        assert "platformforge" not in (mcp.get("mcpServers") or {})


def test_uninstall_ultimo_forge_remove_docs_gerados(project: Path) -> None:
    service.install(scope="project", root=project, yes=True)
    service.uninstall(scope="project", root=project)
    assert not (project / "AGENT_PROTOCOL.md").exists()
    assert not (project / "AGENTS.md").exists()
    assert not (project / "CLAUDE.md").exists()
    assert not (project / ".mcp.json").exists()


def test_install_recusa_marcador_ambiguo(project: Path) -> None:
    (project / "AGENTS.md").write_text(
        "# x\n<!-- forge:platform-forge:begin -->\na\n"
        "<!-- forge:platform-forge:begin -->\nb\n"
        "<!-- forge:platform-forge:end -->\n",
        encoding="utf-8")
    out = service.install(scope="project", root=project, yes=True)
    check = next(
        (c for c in out["checks"] if c["id"] == "context-registry"), None)
    assert check is not None and check["status"] == "BLOCKED"
    assert "FORGE-CONTEXT-CONFLICT" in check["detail"]


def test_install_recusa_protocolo_estrangeiro(project: Path) -> None:
    (project / "AGENT_PROTOCOL.md").write_text("# protocolo proprio\n",
                                             encoding="utf-8")
    out = service.install(scope="project", root=project, yes=True)
    check = next(
        (c for c in out["checks"] if c["id"] == "context-registry"), None)
    assert check is not None and check["status"] == "BLOCKED"
    assert (project / "AGENT_PROTOCOL.md").read_text(
        encoding="utf-8") == "# protocolo proprio\n"


def test_repair_reconstroi_doc_e_mcp(project: Path) -> None:
    service.install(scope="project", root=project, yes=True)
    (project / "AGENTS.md").unlink()
    (project / ".mcp.json").unlink()
    out = service.repair(scope="project", root=project)
    assert out["status"] == "completed"
    ids = {c["id"]: c["status"] for c in out["checks"]}
    assert ids.get("consumer-docs") == "PASS"
    assert ids.get("mcp-json") == "PASS"
    assert "forge:platform-forge:begin" in (
        project / "AGENTS.md").read_text(encoding="utf-8")
    import json
    mcp = json.loads((project / ".mcp.json").read_text(encoding="utf-8"))
    assert mcp["mcpServers"]["platformforge"]["command"] == "platformforge-mcp"


def test_uninstall_sem_estado_limpa_residuo_docs(project: Path) -> None:
    """State dir removido a mao: residuos de contexto/docs ainda sao
    limpos pelo caminho de leftovers; root pristino nao ganha
    `.forge/context`."""
    import shutil

    service.install(scope="project", root=project, yes=True)
    shutil.rmtree(project / ".platformforge")
    out = service.uninstall(scope="project", root=project)
    assert out["status"] == "completed"
    assert not (project / "AGENT_PROTOCOL.md").exists()
    assert "forge:platform-forge" not in (
        project / "AGENTS.md").read_text(encoding="utf-8") \
        if (project / "AGENTS.md").exists() else True

    pristine = project / "pristine"
    pristine.mkdir()
    (pristine / ".git").mkdir()
    service.uninstall(scope="project", root=pristine)
    assert not (pristine / ".forge").exists()
