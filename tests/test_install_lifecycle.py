"""PORTABLE_INSTALL_LIFECYCLE — ``platformforge install`` forge/* surface.

Adapter over ``platformforge.distribution`` plan/apply/uninstall/upgrade +
vendored installkit: dry-run plans, approval refusal, managed apply,
health docs, drift/repair, reversible uninstall, and MCP handshake.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from platformforge.install import service


@pytest.fixture(autouse=True)
def _forge_home_isolado(tmp_path: Path,
                        monkeypatch: pytest.MonkeyPatch) -> None:
    """install-2.1: successful project/workspace installs re-assert
    ``~/.forge/installations/platform-forge.json`` — keep the account
    registry out of the real HOME (kit honors FORGE_HOME_OVERRIDE)."""
    monkeypatch.setenv("FORGE_HOME_OVERRIDE",
                       str(tmp_path / "forge-home"))


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


def test_project_scope_requires_repo(tmp_path: Path,
                                     monkeypatch: pytest.MonkeyPatch) -> None:
    """install-2.1: refusal only fires on the IMPLICIT cwd path — a bare
    directory with no member marker. An explicit ``--root`` is
    authoritative (the caller declared the target; gitless dirs are
    first-class), matching ``kit.resolve_scope``."""
    plain = tmp_path / "not-a-repo"
    plain.mkdir()
    monkeypatch.chdir(plain)
    with pytest.raises(service.InstallRefusal) as exc:
        service.install(scope="project", root=None, yes=True)
    assert exc.value.kind == "FORGE-INSTALL-NOT-A-REPO"


def test_project_scope_explicit_root_needs_no_marker(tmp_path: Path) -> None:
    """install-2.1 gitless parity: explicit --root to a markerless dir is
    honored verbatim (kit.resolve_scope: explicit wins)."""
    plain = tmp_path / "fresh-target"
    plain.mkdir()
    doc = service.install(scope="project", root=plain, dry_run=True)
    assert doc["status"] == "planned"
    assert doc["target_root"] == str(plain.resolve())


def test_project_scope_gitless_markers_accepted(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Implicit cwd resolution accepts any kit MEMBER_MARKERS hit —
    pyproject.toml/forge.json/package.json without .git (gitless
    members are first-class, install-2.1)."""
    for marker in ("pyproject.toml", "forge.json", "package.json"):
        d = tmp_path / marker.replace(".", "_")
        d.mkdir()
        (d / marker).write_text("{}\n" if marker.endswith("json")
                               else "[project]\nname='x'\n")
        monkeypatch.chdir(d)
        doc = service.install(scope="project", root=None, dry_run=True)
        assert doc["status"] == "planned", marker
        assert doc["target_root"] == str(d.resolve())


def test_workspace_scope_explicit_root_never_climbs(tmp_path: Path) -> None:
    """install-2.1: the ancestor `.platformforge/workspace.json` walk must
    never override an explicit --root — a member dir inside a workspace
    stays the target."""
    ws = tmp_path / "ws"
    member = ws / "sub" / "member"
    member.mkdir(parents=True)
    (ws / ".platformforge").mkdir(parents=True)
    (ws / ".platformforge" / "workspace.json").write_text("{}")
    doc = service.install(scope="workspace", root=member, dry_run=True)
    assert doc["target_root"] == str(member.resolve())


def test_workspace_scope_implicit_walk_still_discovers(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Without --root the ancestor walk keeps its discovery semantics —
    cwd inside a workspace resolves the workspace root."""
    ws = tmp_path / "ws"
    member = ws / "sub" / "member"
    member.mkdir(parents=True)
    (ws / ".platformforge").mkdir(parents=True)
    (ws / ".platformforge" / "workspace.json").write_text("{}")
    monkeypatch.chdir(member)
    doc = service.install(scope="workspace", root=None, dry_run=True)
    assert doc["target_root"] == str(ws.resolve())


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
    assert Path(mcp["mcpServers"]["platformforge"]["command"]).is_absolute()
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
    assert Path(mcp["mcpServers"]["platformforge"]["command"]).is_absolute()


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


# --- install-2.1 (cycle-16 wave-05) ----------------------------------------


def test_dry_run_planned_files_are_contract_dicts(project: Path) -> None:
    """planned_files must carry {path,kind,action,sha256} — the-forge's
    _collect_forge_plan reads exactly this shape; strings make the
    cross-forge conflict detection blind."""
    doc = service.install(scope="project", root=project, dry_run=True)
    assert doc["planned_files"]
    for f in doc["planned_files"]:
        assert {"path", "kind", "action", "sha256"} <= set(f)
        assert f["action"] in ("create", "update", "conflict")
        assert len(f["sha256"]) == 64


def test_cli_root_flag_accepted_and_preferred(
        project: Path, tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str]) -> None:
    """the-forge's orchestrator always sends --root — the flag must parse
    (was rc=2) and win over a stray --repo."""
    import json

    from platformforge.cli.main import main

    work = tmp_path / "cwd"
    work.mkdir()
    monkeypatch.chdir(work)
    other = tmp_path / "other"
    other.mkdir()
    rc = main(["install", "--root", str(project), "--repo", str(other),
               "--dry-run"])
    assert rc == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["status"] == "planned"
    assert doc["target_root"] == str(project.resolve())


def test_cli_dry_run_writes_no_state(project: Path, tmp_path: Path,
                                     monkeypatch: pytest.MonkeyPatch,
                                     capsys: pytest.CaptureFixture[str]) -> None:
    """A plan writes NOTHING — no .platformforge state at the target and
    no audit receipt under --repo (ReceiptWriter suppressed on dry-run)."""
    from platformforge.cli.main import main

    work = tmp_path / "cwd"
    work.mkdir()
    monkeypatch.chdir(work)
    rc = main(["install", "--root", str(project), "--dry-run"])
    assert rc == 0
    capsys.readouterr()
    assert not (project / ".platformforge").exists()
    assert not (work / ".platformforge").exists()


def test_mcp_json_blocked_is_fail_closed(project: Path) -> None:
    """install-2.1: a BLOCKED mandatory post-check (mcp-json) flips the
    receipt to failed + verification FAIL — never completed+PASS."""
    (project / ".mcp.json").write_text("not-json{{{", encoding="utf-8")
    doc = service.install(scope="project", root=project, yes=True)
    check = next(c for c in doc["checks"] if c["id"] == "mcp-json")
    assert check["status"] == "BLOCKED"
    assert doc["status"] == "failed"
    assert doc["verification"]["status"] == "FAIL"


def test_context_blocked_is_fail_closed(project: Path) -> None:
    """Same rule for context-registry BLOCKED (ambiguous foreign marker):
    verification must reflect checks appended after the receipt build."""
    (project / "AGENT_PROTOCOL.md").write_text("# protocolo proprio\n",
                                             encoding="utf-8")
    doc = service.install(scope="project", root=project, yes=True)
    assert any(c["status"] == "BLOCKED" for c in doc["checks"])
    assert doc["status"] == "failed"
    assert doc["verification"]["status"] == "FAIL"


def test_dry_run_verification_is_unverified(project: Path) -> None:
    doc = service.install(scope="project", root=project, dry_run=True)
    assert doc["verification"]["status"] == "UNVERIFIED"


def test_profile_minimal_filters_assets(project: Path) -> None:
    """PROFILE_COMPONENTS: minimal keeps core+mcp — no skill/agent writes."""
    doc = service.install(scope="project", root=project,
                          profile="minimal", yes=True)
    assert doc["status"] == "completed"
    assert not (project / ".agents" / "skills").exists()
    assert not (project / ".agents" / "agents").exists()
    # mcp is in minimal's kind set — the workspace-local hint is written
    # and the managed .mcp.json key is asserted.
    assert (project / ".platformforge" / "mcp.json").is_file()
    ids = {c["id"] for c in doc["checks"]}
    assert "mcp-json" in ids


def test_components_selection_filters_writes(project: Path) -> None:
    """--components overrides by kind: skills-only writes no mcp surface."""
    doc = service.install(scope="project", root=project,
                          components=("skills",), yes=True)
    assert doc["status"] == "completed"
    assert (project / ".agents" / "skills").exists()
    assert not (project / ".mcp.json").exists()
    assert "mcp-json" not in {c["id"] for c in doc["checks"]}


def test_components_unknown_refused(project: Path) -> None:
    with pytest.raises(service.InstallRefusal) as exc:
        service.install(scope="project", root=project,
                        components=("bogus",), yes=True)
    assert exc.value.kind == "FORGE-INSTALL-PROFILE-UNKNOWN"


def test_install_registers_declared_install_surface(
        project: Path, tmp_path: Path) -> None:
    """A completed project install re-asserts the account manifest with
    the forge.json install-2.1 declarations (verbatim, never
    fabricated) — sibling parity: aws/azure do the same."""
    import json

    from platformforge import _installkit as kit

    doc = service.install(scope="project", root=project, yes=True)
    assert doc["status"] == "completed"
    manifest = json.loads(
        (kit.installations_dir() / "platform-forge.json").read_text(
            encoding="utf-8"))
    assert manifest["schema"] == "forge/InstallationManifest/v1"
    assert manifest["installation_kind"] == "content"
    assert manifest["depends_on"] == []
    surf = manifest["install"]
    assert "--root" in surf["flags"] and "--scope" in surf["flags"]
    assert surf["approval"] == "--yes"
    assert surf["scopes"] == ["project", "workspace", "user"]
    assert manifest["mcp"]["command"] == ["platformforge-mcp"]
    assert manifest["mcp"]["verify_tool"] == "platformforge_inspect"


def test_failed_install_does_not_register(project: Path,
                                          tmp_path: Path) -> None:
    """Fail-closed: a BLOCKED post-check keeps status=failed — no account
    manifest is (re-)asserted for an install that did not complete."""
    from platformforge import _installkit as kit

    (project / ".mcp.json").write_text("not-json{{{", encoding="utf-8")
    doc = service.install(scope="project", root=project, yes=True)
    assert doc["status"] == "failed"
    assert not (kit.installations_dir() / "platform-forge.json").exists()


# --- cycle-16.1 wave-06: forge/InstallLifecycle/v1 + incremental reinstall ---


def test_receipt_carries_install_lifecycle_block(project: Path) -> None:
    """forge/InstallLifecycle/v1 — every emitted receipt carries the
    derived lifecycle view: dry-run plans are `planned`, a verified
    apply is `verified` (never `completed` — that stays in status)."""
    plan = service.install(scope="project", root=project, dry_run=True)
    assert plan["lifecycle"]["schema"] == "forge/InstallLifecycle/v1"
    assert plan["lifecycle"]["state"] == "planned"

    doc = service.install(scope="project", root=project, yes=True)
    assert doc["status"] == "completed"
    assert doc["verification"]["status"] == "PASS"
    assert doc["lifecycle"]["state"] == "verified"


def test_failed_install_lifecycle_is_failed(project: Path) -> None:
    """A BLOCKED mandatory post-check flips status to failed — and the
    derived lifecycle follows the FINAL verdict, not the first build."""
    (project / ".mcp.json").write_text("not-json{{{", encoding="utf-8")
    doc = service.install(scope="project", root=project, yes=True)
    assert doc["status"] == "failed"
    assert doc["lifecycle"]["state"] == "failed"


def test_health_docs_carry_lifecycle_block(project: Path) -> None:
    """InstallationHealth docs map onto the same lifecycle: healthy →
    ready, degraded → partially_applied, no evidence → unverified."""
    st = service.status(scope="project", root=project)
    assert st["lifecycle"]["schema"] == "forge/InstallLifecycle/v1"
    assert st["lifecycle"]["state"] == "unverified"

    doc = service.install(scope="project", root=project, yes=True)
    st = service.status(scope="project", root=project)
    assert st["status"] == "healthy"
    assert st["lifecycle"]["state"] == "ready"
    dr = service.doctor(scope="project", root=project)
    assert dr["lifecycle"]["state"] in ("ready", "partially_applied",
                                       "unverified", "failed")

    victim = project / next(p for p in doc["managed_files"]
                            if "skills/" in p)
    victim.write_text("user drift\n", encoding="utf-8")
    st = service.status(scope="project", root=project)
    assert st["status"] == "degraded"
    assert st["lifecycle"]["state"] == "partially_applied"


def test_lifecycle_derivation_closed_vocabulary() -> None:
    """Derivation unit checks — every output stays inside the closed
    v1 vocabulary; declined/refused receipts derive ``blocked``."""
    from platformforge.install import lifecycle as lc

    for doc, want in (
        ({"status": "planned"}, "planned"),
        ({"status": "declined"}, "blocked"),
        ({"status": "refused"}, "blocked"),
        ({"status": "completed",
          "verification": {"status": "PASS"}}, "verified"),
        ({"status": "completed",
          "verification": {"status": "FAIL"}}, "failed"),
        ({"status": "completed"}, "applied"),
        ({"status": "failed"}, "failed"),
        ({"status": "unverified"}, "unverified"),
        ({"forges": [{"status": "completed"}, {"status": "failed"}],
          "status": "completed",
          "verification": {"status": "PASS"}}, "partially_applied"),
    ):
        state, _detail = lc.receipt_state(doc)
        assert state == want, (doc, state)
        assert state in lc.STATES
    for doc, want in (
        ({"status": "healthy"}, "ready"),
        ({"status": "degraded"}, "partially_applied"),
        ({"status": "broken"}, "failed"),
        ({"status": "unverified"}, "unverified"),
    ):
        state, _detail = lc.health_state(doc)
        assert state == want, (doc, state)
        assert state in lc.STATES


def test_reinstall_does_not_rewrite_identical_assets(project: Path) -> None:
    """Incremental reinstall (cycle 16.1 §7.4): a second install plans
    every byte-identical asset as `identical` — and does NOT re-write
    them on disk (mtimes stay untouched)."""
    doc = service.install(scope="project", root=project, yes=True)
    managed = doc["managed_files"]
    assert managed
    mtimes = {p: (project / p).stat().st_mtime_ns for p in managed}

    again = service.install(scope="project", root=project, yes=True)
    plan = again["plan"]
    assert not plan["creates"], plan["creates"]
    assert not plan["managed_updates"], plan["managed_updates"]
    assert not plan["conflicts"], plan["conflicts"]
    assert sorted(plan["identical"]) == sorted(managed)
    for rel, before in mtimes.items():
        after = (project / rel).stat().st_mtime_ns
        assert after == before, f"{rel} was re-written"
