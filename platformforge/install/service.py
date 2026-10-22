"""``forge/*``-contract install lifecycle for Platform Forge.

Adapter over the repository's own distribution engine
(``platformforge.distribution.service``: plan/apply/uninstall/upgrade/
doctor with per-file sha256 tracking) plus the vendored shared installkit
(scope resolution, locks, MCP handshake, ``~/.forge`` registry) — same
surface as every sibling Forge.

Profiles map onto the native ``agentic`` distribution profile (Platform
Forge ships one asset set; the contract profile is recorded in the
receipt for cross-forge tooling). ``copilot`` maps onto the generic
``agents`` mirror root — ``.agents/`` is exactly what it is for.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from platformforge import __version__, discovery_ops
from platformforge import _forgecontext as fctx
from platformforge import _installkit as kit

FORGE_ID = "platform-forge"
PROFILES: tuple[str, ...] = ("minimal", "recommended", "full")
GATEWAY_PROFILES: tuple[str, ...] = ("economy", "balanced", "deep")
SCOPES: tuple[str, ...] = ("project", "workspace", "user")
CONTRACT_HOSTS: tuple[str, ...] = ("claude", "devin", "codex", "copilot")
# contract host -> native host prefix(es)
_HOST_MAP: dict[str, str] = {
    "claude": "claude",
    "devin": "devin",
    "codex": "codex",
    "copilot": "agents",
}


class InstallRefusal(Exception):
    """Named refusal carrying the forge/* kind vocabulary."""

    def __init__(self, kind: str, detail: str) -> None:
        super().__init__(detail)
        self.kind = kind
        self.detail = detail


def _spec() -> kit.ForgeSpec:
    return kit.ForgeSpec(
        forge_id=FORGE_ID,
        package="platformforge",
        distribution="platformforge",
        cli_name="platformforge",
        python_spec=">=3.10",
        state_dir=".platformforge",
        mcp_command=("platformforge-mcp",),
        mcp_server_name="platformforge",
        mcp_verify_tool="platformforge_inspect",
        version_cmd=("--version",),
        render_assets=None,
        marker_files=(),
        marker_body="",
        user_state_dir="~/.platformforge",
    )


def _resolve(scope: str, root: Path | None) -> Path:
    if scope not in SCOPES:
        raise InstallRefusal(kit.E_SCOPE, f"scope {scope!r}; expected {SCOPES}")
    if scope == "user":
        return Path.home()
    if scope == "project":
        t = Path(root).resolve() if root else Path.cwd().resolve()
        if not (t / ".git").exists() and not (t / "forge.json").exists():
            raise InstallRefusal(
                kit.E_NOTREPO,
                f"{t} is not a repository root (no .git / forge.json)")
        return t
    # workspace: reuse existing manifest when present. Fresh directories are
    # valid workspace targets; apply_install creates manifest atomically.
    t = Path(root).resolve() if root else Path.cwd().resolve()
    for cand in (t, *t.parents):
        if (cand / ".platformforge" / "workspace.json").is_file():
            return cand
    return t


def _hosts(host: str) -> list[str]:
    """``all`` → todos; ``none``/vazio → opt-out explícito (nunca todos);
    nome único ou csv → subconjunto validado (GAP-003)."""
    if host == "all":
        return sorted(set(_HOST_MAP.values()))
    if not host or host == "none":
        return []
    nomes = [h.strip() for h in host.split(",") if h.strip()]
    out: list[str] = []
    for nome in nomes:
        # Native host names pass through (legacy CLI compat); contract names map.
        if nome in _HOST_MAP.values():
            out.append(nome)
        elif nome in _HOST_MAP:
            out.append(_HOST_MAP[nome])
        else:
            raise InstallRefusal(
                kit.E_HOST, f"host {nome!r}; expected {CONTRACT_HOSTS} + all,none")
    return list(dict.fromkeys(out))


def _profile(profile: str) -> str:
    if profile not in PROFILES:
        raise InstallRefusal(
            kit.E_PROFILE, f"profile {profile!r}; expected {PROFILES}")
    return profile


def _gateway_profile(profile: str) -> str:
    if profile not in GATEWAY_PROFILES:
        raise InstallRefusal(
            kit.E_PROFILE,
            f"gateway_profile {profile!r}; expected {GATEWAY_PROFILES}",
        )
    return profile


def _receipt(operation: str, scope: str, target: Path, *,
             status: str, checks: list[dict[str, Any]],
             managed_files: list[str] | None = None,
             extra: dict[str, Any] | None = None) -> dict[str, Any]:
    doc = {
        "schema": kit.SCHEMA_RECEIPT, "forge_id": FORGE_ID,
        "operation": operation, "scope": scope,
        "target_root": str(target), "managed_files": managed_files or [],
        "checks": checks,
        "verification": {"status": "PASS" if all(
            c["status"] in ("PASS", "NOT_APPLICABLE", "UNVERIFIED", "BLOCKED")
            for c in checks) else "FAIL"},
        "status": status, "created_at": kit._utc_now(),
        "created_by": f"platformforge/{__version__}",
    }
    if extra:
        doc.update(extra)
    return doc


def install(*, scope: str = "project", root: Path | None = None,
            host: str = "all", profile: str = "recommended",
            yes: bool = False, dry_run: bool = False,
            components: tuple[str, ...] | None = None,
            gateway_profile: str = "balanced") -> dict[str, Any]:
    """``platformforge install`` — governed apply over ``apply_install``."""
    from platformforge.distribution.service import apply_install, plan_install

    _profile(profile)  # validates; native profile is always "agentic"
    _gateway_profile(gateway_profile)
    opts = kit.component_options("recommended", components)
    opts["execution_profile"] = gateway_profile
    native_hosts = _hosts(host)
    target = _resolve(scope, root)
    state = target / ".platformforge"
    if dry_run:
        plan, _manifest, _assets = plan_install(target, "agentic",
                                              native_hosts)
        return _receipt(
            "install", scope, target, status="planned",
            checks=[{"id": "plan", "status": "UNVERIFIED",
                     "detail": "dry-run — nothing written"}],
            extra={"dry_run": True,
                   "components": opts or None,
                   "gateway_profile": gateway_profile,
                   "planned_files": sorted(plan.creates + plan.managed_updates),
                   "conflicts": plan.conflicts})
    if not yes:
        raise InstallRefusal(
            kit.E_NOTAPPROVED,
            "install requires --yes or --dry-run; the plan is the contract")
    with kit.acquire_lock(state):
        out = apply_install(target, "agentic", native_hosts)
    if opts:
        state.mkdir(parents=True, exist_ok=True)
        (kit.components_path(state)).write_text(
            json.dumps(opts, indent=2), encoding="utf-8")
    if "refusal" in out:
        return _receipt(
            "install", scope, target, status="failed",
            checks=[{"id": "apply", "status": "FAIL",
                     "detail": f"{out['refusal']}: {out.get('conflicts')}"}])
    receipt = out.get("receipt") or {}
    doc = _receipt(
        "install", scope, target, status="completed",
        checks=[{"id": "apply", "status": "PASS",
                 "detail": f"{len(receipt.get('files', {}))} managed files"}],
        managed_files=sorted(receipt.get("files", {})),
        extra={"plan": out.get("plan"), "profile": profile,
               "components": opts or None,
               "gateway_profile": gateway_profile})
    contract_hosts = sorted(
        {next((c for c, n in _HOST_MAP.items() if n == h), h)
         for h in native_hosts}
    )
    if _mcp_enabled(opts):
        doc.setdefault("checks", []).append(_mcp_set_project(target))
    _register_context(
        target, doc, scope=scope, profile=profile,
        hosts=contract_hosts, components=opts or None,
    )
    return doc


def _read_receipt(target: Path) -> dict[str, Any]:
    path = target / ".platformforge" / "install-receipt.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def status(*, scope: str = "project", root: Path | None = None) -> dict[str, Any]:
    target = _resolve(scope, root)
    rec = _read_receipt(target)
    if not rec:
        return {
            "schema": kit.SCHEMA_HEALTH, "forge_id": FORGE_ID,
            "status": "unverified", "target_root": str(target),
            "checks": [{"id": "receipt", "status": "UNVERIFIED",
                        "detail": "no install receipt"}],
            "checked_at": kit._utc_now(),
            "repair_hint": "platformforge install --yes",
        }
    from platformforge.distribution.service import doctor as dist_doctor

    doc = dist_doctor(target)
    healthy = doc.get("state") == "healthy"
    drifted = bool(doc.get("drift") or doc.get("missing"))
    return {
        "schema": kit.SCHEMA_HEALTH, "forge_id": FORGE_ID,
        "status": "healthy" if healthy else "degraded",
        "target_root": str(target),
        "checks": [{"id": f"pf:{k}", "status": "PASS" if v else "FAIL",
                    "detail": str(v)} for k, v in doc.get("checks", {}).items()],
        "distribution": doc,
        "checked_at": kit._utc_now(),
        "repair_hint": "platformforge install repair" if drifted else None,
    }


def doctor(*, scope: str = "project", root: Path | None = None) -> dict[str, Any]:
    target = _resolve(scope, root)
    from platformforge.distribution.service import doctor as dist_doctor

    doc = dist_doctor(target)
    checks = [{"id": f"pf:{k}", "status": "PASS" if v else "FAIL",
               "detail": str(v)} for k, v in doc.get("checks", {}).items()]
    for rel in doc.get("missing", []):
        checks.append({"id": f"missing:{rel}", "status": "FAIL",
                       "detail": "managed file missing"})
    for rel in doc.get("drift", []):
        checks.append({"id": f"drift:{rel}", "status": "FAIL",
                       "detail": "managed file modified"})
    checks.append(kit.mcp_verify(_spec()))
    failed = any(c["status"] == "FAIL" for c in checks)
    return {
        "schema": kit.SCHEMA_HEALTH, "forge_id": FORGE_ID,
        "status": "degraded" if failed else (
            "healthy" if doc.get("state") == "healthy" else "unverified"),
        "target_root": str(target), "checks": checks,
        "distribution": doc,
        "checked_at": kit._utc_now(),
        "repair_hint": "platformforge install repair" if failed else None,
    }


def repair(*, scope: str = "project", root: Path | None = None,
           dry_run: bool = False) -> dict[str, Any]:
    target = _resolve(scope, root)
    from platformforge.distribution.service import doctor as dist_doctor

    before = dist_doctor(target)
    missing = sorted(before.get("missing", []))
    modified = sorted(before.get("drift", []))
    if not _read_receipt(target):
        raise InstallRefusal(kit.E_NOTINSTALLED,
                             "nothing installed — platformforge install --yes")
    if dry_run:
        return _receipt("repair", scope, target, status="planned",
                        checks=[{"id": "drift", "status": "UNVERIFIED",
                                 "detail": f"{len(missing)} missing, "
                                           f"{len(modified)} modified"}],
                        extra={"dry_run": True, "missing": missing,
                               "modified": modified})
    state = target / ".platformforge"
    with kit.acquire_lock(state):
        # apply_install refuses the whole plan when user-modified managed
        # files exist; for repair we restore ONLY the missing entries —
        # conflicts stay untouched (they are user content by contract).
        from platformforge.distribution.service import (
            apply_install,
            plan_install,
        )
        old_rec = _read_receipt(target)
        hosts = old_rec.get("hosts") or ["agents"]
        plan, _manifest, assets = plan_install(target, "agentic", hosts)
        restored: list[str] = []
        if not plan.conflicts:
            out = apply_install(target, "agentic", hosts)
            if "refusal" in out:
                return _receipt(
                    "repair", scope, target, status="failed",
                    checks=[{"id": "repair", "status": "FAIL",
                             "detail": out["refusal"]}])
            restored = sorted(plan.creates + plan.managed_updates)
        else:
            from platformforge.distribution.service import (
                _safe_target,
                _sha,
            )
            rec = _read_receipt(target)
            for rel in plan.creates:
                dest = _safe_target(target, rel)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(assets[rel])
                if _sha(dest.read_bytes()) == _sha(assets[rel]):
                    rec.setdefault("files", {})[rel] = _sha(assets[rel])
                    restored.append(rel)
            (state / "install-receipt.json").write_text(
                json.dumps(rec, indent=2, sort_keys=True) + "\n",
                encoding="utf-8")
    after = dist_doctor(target)
    remaining = sorted(after.get("missing", []))
    kept = sorted(set(after.get("drift", [])))
    checks = [{"id": "repair",
               "status": "PASS" if not remaining else "FAIL",
               "detail": f"{len(missing)} missing restored, "
                         f"{len(remaining)} remaining; "
                         f"{len(kept)} user-modified preserved"}]
    # Consumer docs: re-assert dos blocos `forge:*` a partir dos manifests
    # em `.forge/context/`; recusa nomeada vira check BLOCKED. Escopo user
    # nunca registra contexto — so roda quando ha residuo.
    if scope != "user" and _docs_leftovers(target):
        try:
            out_docs = fctx.repair_docs(target)
            checks.append({
                "id": "consumer-docs",
                "status": "PASS",
                "detail": f"{out_docs['status']} "
                          f"({len(out_docs['written'])} writes)",
            })
        except fctx.ContextError as exc:
            checks.append({
                "id": "consumer-docs",
                "status": "BLOCKED",
                "detail": f"{exc.kind}: {exc.detail}",
            })
    # `.mcp.json` managed key: re-assert when the recorded component set
    # enables mcp and the key is missing/drifted.
    stored = kit.load_components(state)
    if _mcp_enabled(stored) and _mcp_current(target) != _MCP_ENTRY:
        checks.append(_mcp_set_project(target))
    # Modified managed files are user content by the platform-forge
    # ownership contract — preserved, never force-rewritten.
    return _receipt(
        "repair", scope, target,
        status="completed" if not remaining else "failed",
        checks=checks,
        extra={"repaired": [r for r in restored if r not in remaining],
               "kept": kept})


def uninstall(*, scope: str = "project", root: Path | None = None,
              purge: bool = False, dry_run: bool = False) -> dict[str, Any]:
    from platformforge.distribution.service import uninstall as dist_uninstall

    target = _resolve(scope, root)
    if dry_run:
        rec = _read_receipt(target)
        return _receipt("uninstall", scope, target, status="planned",
                        checks=[{"id": "uninstall", "status": "UNVERIFIED",
                                 "detail": f"{len(rec.get('files', {}))} files"}],
                        extra={"dry_run": True,
                               "planned_remove": sorted(rec.get("files", {}))})
    state = target / ".platformforge"
    if not state.exists():
        # No-op idempotente que nao escreve estado — a menos que restem
        # residuos de contexto/docs (state dir sumiu mas a entry no
        # registry ou os blocos `forge:*` continuam). As ops de contexto
        # adquirem lock, entao so rodam quando ha residuo.
        checks = [{"id": "uninstall", "status": "PASS",
                   "detail": "0 removed — nothing installed"}]
        if scope != "user" and _docs_leftovers(target):
            checks += [_unregister_context(target), _uninstall_docs(target)]
        checks.append(_mcp_unset_project(target))
        return _receipt("uninstall", scope, target, status="completed",
                        checks=checks,
                        extra={"removed": [], "kept": []})
    with kit.acquire_lock(state):
        out = dist_uninstall(target, purge=purge)
    if "refusal" in out:
        return _receipt("uninstall", scope, target, status="failed",
                        checks=[{"id": "uninstall", "status": "FAIL",
                                 "detail": out["refusal"]}])
    removed = out.get("removed", [])
    kit._prune_empty_dirs(target, removed)
    checks = [{"id": "uninstall", "status": "PASS",
               "detail": f"{len(removed)} removed, "
                         f"{len(out.get('preserved_modified', []))} preserved"}]
    if scope != "user" and _docs_leftovers(target):
        checks += [_unregister_context(target), _uninstall_docs(target)]
    checks.append(_mcp_unset_project(target))
    return _receipt(
        "uninstall", scope, target, status="completed",
        checks=checks,
        extra={"removed": removed,
               "kept": out.get("preserved_modified", [])})


def update(*, to: str | None = None, repo: Path | None = None,
           dry_run: bool = False) -> dict[str, Any]:
    if to == "latest":
        return _receipt("update", "user", Path.home(), status="failed",
                        checks=[{"id": "version", "status": "FAIL",
                                 "detail": "'latest' is never installable"}])
    manifest = kit._load_json(
        kit.installations_dir() / f"{FORGE_ID}.json", None) or {}
    src = repo or (Path(p) if (p := (manifest.get("source") or {}).get("path"))
                   else None)
    venv = manifest.get("venv")
    if src is None or not src.exists() or not venv:
        return _receipt(
            "update", "user", Path.home(), status="failed",
            checks=[{"id": "source", "status": "BLOCKED",
                     "detail": "no registered checkout/venv — run setup"}])
    venv_py = Path(venv) / ("Scripts/python.exe" if sys.platform == "win32"
                            else "bin/python")
    cmd = [str(venv_py), "-m", "pip", "install", "--upgrade", str(src)]
    if dry_run:
        return _receipt("update", "user", Path.home(), status="planned",
                        checks=[{"id": "pip", "status": "UNVERIFIED",
                                 "detail": " ".join(cmd)}],
                        extra={"dry_run": True})
    proc = subprocess.run(
        cmd, capture_output=True, text=True, timeout=900, check=False)
    return _receipt(
        "update", "user", Path.home(),
        status="completed" if proc.returncode == 0 else "failed",
        checks=[{"id": "pip",
                 "status": "PASS" if proc.returncode == 0 else "FAIL",
                 "detail": (proc.stdout or proc.stderr)[-300:]}])


def mcp_verify() -> dict[str, Any]:
    return kit.mcp_verify(_spec())


__all__ = [
    "CONTRACT_HOSTS",
    "PROFILES",
    "SCOPES",
    "InstallRefusal",
    "doctor",
    "install",
    "mcp_verify",
    "repair",
    "status",
    "uninstall",
    "update",
]


# --------------------------------------------------------------------------
# forge-context/v1 wiring (install-2.0 ciclo 2, the-forge ADR-0061)
# `.forge/context/` e o registry de workspace compartilhado entre forges.
# Este forge so registra e desregistra o proprio `forge_id`.
# --------------------------------------------------------------------------

_PKG_DIR = Path(__file__).resolve().parents[1]
_REPO_DIR = _PKG_DIR.parent

_PF_DOMAINS: tuple[str, ...] = (
    "platform-engineering",
    "infrastructure-as-code",
    "kubernetes",
    "crossplane",
    "terraform",
    "finops",
    "sre",
    "supply-chain",
)


def _mds(base: Path) -> list[str]:
    return sorted(p.stem for p in base.glob("*.md")) if base.is_dir() else []


def _context_manifest(
    *, scope: str, profile: str, hosts: list[str],
    components: dict[str, Any] | None,
) -> dict[str, Any]:
    """Manifesto forge/context/v1 das fontes reais: `forge.json` +
    `forge.agentic.json` no checkout, roster canonico (`agents.roster`),
    `data_path("portable_skills")` e os grupos de dados do pacote."""
    from platformforge.agents.roster import AGENTS
    from platformforge.resources import data_path

    forge_json = kit._load_json(_REPO_DIR / "forge.json", None)
    forge_json = forge_json if isinstance(forge_json, dict) else None
    agentic = kit._load_json(_REPO_DIR / "forge.agentic.json", None)
    agentic = agentic if isinstance(agentic, dict) else None

    skills_root = data_path("portable_skills")
    skills = (
        sorted(
            d.name for d in skills_root.iterdir()
            if d.is_dir() and (d / "SKILL.md").is_file()
        )
        if skills_root.is_dir()
        else []
    )
    agent_ids = sorted(AGENTS)
    coordinators = sorted(
        s.name
        for s in AGENTS.values()
        if s.role in ("coordinator", "orchestrator", "planner")
    )

    rules_root = data_path("rules")
    rule_areas = (
        sorted(p.stem for p in rules_root.glob("*.yaml"))
        + sorted(p.stem for p in rules_root.glob("**/*.yaml"))
        if rules_root.is_dir()
        else []
    )
    rule_areas = sorted(set(rule_areas))
    knowledge_root = data_path("knowledge")
    providers = (
        [{"id": "knowledge-base", "interface": "bundled"}]
        if knowledge_root.is_dir()
        else []
    )
    evals_root = data_path("evals")
    eval_suites = (
        [
            {"id": p.name, "kind": "output-verification"}
            for p in sorted(evals_root.iterdir())
            if p.is_dir()
        ]
        if evals_root.is_dir()
        else []
    )

    checks: list[dict[str, Any]] = [
        {
            "id": "skills-bundle",
            "status": "PASS" if skills else "UNVERIFIED",
            "detail": f"{len(skills)} skills",
        },
        {
            "id": "agent-specs",
            "status": "PASS" if agent_ids else "UNVERIFIED",
            "detail": f"{len(agent_ids)} roster agents",
        },
        {
            "id": "rules-catalog",
            "status": "PASS" if rule_areas else "UNVERIFIED",
            "detail": f"{len(rule_areas)} rule files",
        },
    ]
    return fctx.build_manifest(
        forge_id=FORGE_ID,
        name="Platform Forge",
        version=__version__,
        cli="platformforge",
        package="platformforge",
        distribution="platformforge",
        python_spec=">=3.10",
        scope=scope,
        profile=profile,
        hosts=hosts,
        forge_json=forge_json,
        agentic=agentic,
        domains=_PF_DOMAINS,
        skills=skills,
        coordinators=coordinators,
        agents=agent_ids,
        rule_areas=rule_areas,
        knowledge_providers=providers,
        eval_suites=eval_suites,
        protocols=(
            {"id": "forge/v1", "version": "1"},
            {"id": "forge/context/v1", "version": "1"},
            {"id": "forge/context-registry/v1", "version": "1"},
        ),
        discovery_ops=discovery_ops.ops(),
        discovery_commands=(
            *(
                c
                for c in discovery_ops.commands()
                if c["id"] != "doctor"  # `doctor` declared below
            ),
            {
                "id": "analyze",
                "argv": ["platformforge", "analyze", "{target}"],
                "mode": "direct-capability",
                "read_only": True,
                "description": "analyze platform/IaC surfaces",
            },
            {
                "id": "capability-list",
                "argv": ["platformforge", "capability", "list"],
                "mode": "direct-capability",
                "read_only": True,
                "description": "capability surface inventory",
            },
            {
                "id": "forge-manifest",
                "argv": ["platformforge", "forge", "manifest"],
                "mode": "direct-capability",
                "read_only": True,
                "description": "emitted forge manifest",
            },
            {
                "id": "doctor",
                "argv": ["platformforge", "doctor"],
                "mode": "diagnostic-only",
                "read_only": True,
                "description": "environment + installation health",
            },
        ),
        mcp={
            "server_name": "platformforge",
            "command": ["platformforge-mcp"],
            "verify_tool": "platformforge_inspect",
        },
        resources={
            "skills-bundle": {
                "kind": "bundled",
                "location": "platformforge/data/portable_skills",
                "optional": False,
            },
            "agents-roster": {
                "kind": "bundled",
                "location": "platformforge/agents/roster.py",
                "optional": False,
            },
            "rules-catalog": {
                "kind": "bundled",
                "location": "platformforge/data/rules",
                "optional": False,
            },
            "knowledge-base": {
                "kind": "bundled",
                "location": "platformforge/data/knowledge",
                "optional": True,
            },
            "install-state": {
                "kind": "referenced",
                "location": ".platformforge",
                "optional": True,
            },
        },
        mutating_verbs=(
            "install",
            "uninstall",
            "repair",
            "integrate",
            "detach",
            "collect",
            "case update",
            "change apply",
        ),
        requires_approval=(
            "install", "uninstall", "integrate", "detach", "change apply"
        ),
        offline_available=True,
        health={
            "status": (
                "healthy" if skills and agent_ids and rule_areas else "degraded"
            ),
            "checks": checks,
        },
        components=components,
        recorded_by="platformforge",
    )


def _register_context(
    target: Path,
    receipt: dict[str, Any],
    *,
    scope: str,
    profile: str,
    hosts: list[str],
    components: dict[str, Any] | None,
) -> None:
    """Grava `.forge/context/` — manifesto + entrada no registry +
    ROUTING.md + os consumer docs (blocos `forge:*` e o AGENT_PROTOCOL.md
    compartilhado). Falha vira check BLOCKED nomeado no recibo.
    Escopo user tem target=~: `~/.forge/` e nivel de conta
    (`installations/`); contexto de workspace nao se escreve la."""
    if scope == "user":
        return
    try:
        manifest = _context_manifest(
            scope=scope, profile=profile, hosts=hosts, components=components
        )
        out = fctx.register_forge(target, manifest, owner=FORGE_ID)
        receipt.setdefault("checks", []).append(
            {
                "id": "context-registry",
                "status": "PASS",
                "detail": f".forge/context {out['status']} "
                f"({len(out['written'])} writes)",
            }
        )
    except fctx.ContextError as exc:
        receipt.setdefault("checks", []).append(
            {"id": "context-registry", "status": "BLOCKED",
             "detail": f"{exc.kind}: {exc.detail}"}
        )
        return
    try:
        docs = fctx.install_docs(target, manifest, owner=FORGE_ID)
        receipt.setdefault("checks", []).append(
            {
                "id": "consumer-docs",
                "status": "PASS",
                "detail": (
                    f"{docs['status']}: {len(docs['written'])} written, "
                    f"{len(docs['kept'])} kept"
                ),
            }
        )
    except fctx.ContextError as exc:
        receipt.setdefault("checks", []).append(
            {"id": "consumer-docs", "status": "BLOCKED",
             "detail": f"{exc.kind}: {exc.detail}"}
        )


def _unregister_context(target: Path) -> dict[str, Any]:
    """Remove somente o manifesto/entry deste forge."""
    try:
        out = fctx.unregister_forge(target, FORGE_ID, owner=FORGE_ID)
        return {
            "id": "context-registry",
            "status": "PASS",
            "detail": f".forge/context {out['status']}",
        }
    except fctx.ContextError as exc:
        return {
            "id": "context-registry",
            "status": "BLOCKED",
            "detail": f"{exc.kind}: {exc.detail}",
        }


# --------------------------------------------------------------------------
# consumer docs + `.mcp.json` managed key — install-2.0 ciclo 3 (lf-0036)
# `install_docs`/`uninstall_docs`/`repair_docs` sao da camada forge_context
# vendored; `.mcp.json` usa `mcp_set`/`mcp_unset` do installkit com
# ownership tracking em `_forge_managed`. platform-forge nunca emitiu
# markers legados — `_LEGACY_DOC_TAGS` fica vazio.
# --------------------------------------------------------------------------

_LEGACY_DOC_TAGS: tuple[str, ...] = ()
_CONSUMER_DOCS: tuple[str, ...] = (
    "AGENTS.md", "CLAUDE.md", "AGENT_PROTOCOL.md")
_MCP_NAME = "platformforge"
_MCP_ENTRY: dict[str, Any] = {"command": "platformforge-mcp", "args": []}


def _docs_leftovers(target: Path) -> bool:
    """True quando o target ainda carrega residuo forge_context — leitura
    sem lock; so um hit justifica o caminho de escrita (nunca criamos
    `.forge/context/` num root pristino)."""
    if (target / fctx.CONTEXT_DIR).exists():
        return True
    needles = (
        f"forge:{FORGE_ID}:", f"{fctx.DOC_TAG_ECOSYSTEM}:",
        fctx.PROTOCOL_SENTINEL,
    )
    for name in _CONSUMER_DOCS:
        path = target / name
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if any(n in text for n in needles):
            return True
    return False


def _uninstall_docs(target: Path) -> dict[str, Any]:
    """Retira os blocos `forge:platform-forge` dos consumer docs — depois
    do unregister, para o protocolo regen sem nos."""
    try:
        out = fctx.uninstall_docs(target, FORGE_ID, owner=FORGE_ID)
        return {
            "id": "consumer-docs",
            "status": "PASS",
            "detail": f"{out['status']}: {len(out['written'])} changed",
        }
    except fctx.ContextError as exc:
        return {
            "id": "consumer-docs",
            "status": "BLOCKED",
            "detail": f"{exc.kind}: {exc.detail}",
        }


def _mcp_enabled(components: dict[str, Any] | None) -> bool:
    """`mcp` e kind de todos os profiles; desligado so quando uma selecao
    explicita de componentes o exclui."""
    kinds = (components or {}).get("asset_kinds")
    return kinds is None or "mcp" in kinds


def _mcp_current(target: Path) -> dict[str, Any] | None:
    doc = kit._load_json(target / ".mcp.json", None)
    if not isinstance(doc, dict):
        return None
    servers = doc.get("mcpServers")
    if not isinstance(servers, dict):
        return None
    entry = servers.get(_MCP_NAME)
    return entry if isinstance(entry, dict) else None


def _mcp_set_project(target: Path) -> dict[str, Any]:
    """Managed `mcpServers.platformforge` no `.mcp.json` compartilhado —
    outros servidores e top-level keys sao preservados."""
    path = target / ".mcp.json"
    cur: dict[str, Any] | None = None
    if path.exists():
        cur = kit._load_json(path, None)
        if not isinstance(cur, dict):
            return {"id": "mcp-json", "status": "BLOCKED",
                    "detail": ".mcp.json exists but is not a JSON object"}
    new = kit.mcp_set(cur, _MCP_NAME, _MCP_ENTRY, FORGE_ID)
    payload = kit._json_bytes(new)
    if path.exists() and path.read_bytes() == payload:
        return {"id": "mcp-json", "status": "PASS",
                "detail": ".mcp.json managed key unchanged"}
    kit._atomic_write(path, payload)
    return {"id": "mcp-json", "status": "PASS",
            "detail": ".mcp.json managed key set (platformforge-mcp)"}


def _mcp_unset_project(target: Path) -> dict[str, Any]:
    """Remove so a nossa managed key; preserva outros servidores. Arquivo
    que so tinha conteudo nosso e removido."""
    path = target / ".mcp.json"
    if not path.exists():
        return {"id": "mcp-json", "status": "PASS", "detail": "absent"}
    cur = kit._load_json(path, None)
    if not isinstance(cur, dict):
        return {"id": "mcp-json", "status": "BLOCKED",
                "detail": ".mcp.json is not a JSON object"}
    servers = cur.get("mcpServers") or {}
    managed = (cur.get("_forge_managed") or {}).get(FORGE_ID) or []
    if _MCP_NAME not in servers and "mcpServers.platformforge" not in managed:
        return {"id": "mcp-json", "status": "PASS", "detail": "key absent"}
    new = kit.mcp_unset(cur, _MCP_NAME, FORGE_ID)
    if new:
        kit._atomic_write(path, kit._json_bytes(new))
    else:
        path.unlink()
    return {"id": "mcp-json", "status": "PASS",
            "detail": ".mcp.json managed key removed"}
