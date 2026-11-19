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
from platformforge.install import lifecycle as _lc

FORGE_ID = "platform-forge"
PROFILES: tuple[str, ...] = ("minimal", "recommended", "full")
GATEWAY_PROFILES: tuple[str, ...] = ("economy", "balanced", "deep")
SCOPES: tuple[str, ...] = ("project", "workspace", "user")
CONTRACT_HOSTS: tuple[str, ...] = ("claude", "devin", "codex", "copilot")

# --------------------------------------------------------------------------
# install-2.1 — declared profile/component semantics (sibling precedent:
# PROFILE_COMPONENTS in sparkforge_aws/azure + apiforge).
#
# `--profile` selects asset-kind SETS — and nothing else. There is no
# per-kind depth: `recommended` and `full` install the SAME file set
# today (declared honestly, same as `kit.profile_asset_kinds`); `full` is
# the slot reserved for heavier optional defaults if they ever ship.
# `minimal` keeps only core + `mcp` — the .mcp.json managed key is config,
# not content. `--components` overrides by kind.
#
# `--gateway-profile` is an ORTHOGONAL dimension: persisted as
# `execution_profile` in components.json for the orchestrator/telemetry.
# platformforge-mcp's argv has NO mode/surface flag today — the profile
# is recorded-only, never faked into argv (install-2.1 finding §8).
# --------------------------------------------------------------------------

# Asset kinds (`kit.COMPONENT_KINDS` + core) each `--profile` enables —
# the same sets as `kit.profile_asset_kinds`, as declared data.
PROFILE_COMPONENTS: dict[str, tuple[str, ...]] = {
    "minimal": ("config", "mcp", "marker", "state"),
    "recommended": (
        "config", "mcp", "marker", "state",
        "skill", "agent", "knowledge", "rules", "evals",
    ),
    "full": (
        "config", "mcp", "marker", "state",
        "skill", "agent", "knowledge", "rules", "evals",
    ),
}
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
        # install-2.1: an explicit --root is authoritative (the caller
        # declared the target — gitless project dirs are first-class).
        # The implicit cwd path still requires a project marker, but the
        # marker set is the kit's MEMBER_MARKERS — pyproject.toml /
        # forge.json / package.json count, .git is not mandatory.
        if root is None and not kit._is_project_root(t):
            raise InstallRefusal(
                kit.E_NOTREPO,
                f"{t} is not a project root (none of {sorted(kit.MEMBER_MARKERS)}); "
                "pass --root to declare the target, or use --scope workspace "
                "for fresh dirs")
        return t
    # workspace: an explicit --root is authoritative — the ancestor
    # `.platformforge/workspace.json` walk can never move the target ABOVE
    # it (install-2.1; parity with kit.resolve_scope). Without --root the
    # walk discovers an existing workspace manifest from cwd; fresh
    # directories remain valid targets (apply creates the manifest).
    t = Path(root).resolve() if root else Path.cwd().resolve()
    if root is not None:
        return t
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


def _verification_status(checks: list[dict[str, Any]]) -> str:
    """Fail-closed aggregation (install-2.1): a check that could not run is
    never a pass. FAIL/BLOCKED → FAIL (a BLOCKED mandatory component is a
    failed verification, not an approved one), UNVERIFIED → UNVERIFIED
    (honest middle state — same three-state rule the consolidated
    workspace receipt uses), PASS/NOT_APPLICABLE → PASS."""
    statuses = {c.get("status") for c in checks}
    if statuses & {"FAIL", "BLOCKED"}:
        return "FAIL"
    if "UNVERIFIED" in statuses:
        return "UNVERIFIED"
    return "PASS"


def _finalize_verification(doc: dict[str, Any]) -> dict[str, Any]:
    """Recompute ``verification`` AFTER all post-checks were appended —
    checks landing after the receipt is built (mcp-json, context-registry,
    consumer-docs) must move the verdict too. A FAIL/BLOCKED check also
    flips a ``completed`` status to ``failed`` — the same rule
    context-registry already applied, now uniform (mcp-json included)."""
    checks = doc.get("checks") or []
    doc["verification"] = {"status": _verification_status(checks)}
    if doc.get("status") == "completed" and any(
        c.get("status") in ("FAIL", "BLOCKED") for c in checks
    ):
        doc["status"] = "failed"
    # The lifecycle view is derived evidence — recompute it AFTER the
    # final status/verification so it never goes stale (install-2.1 +
    # forge/InstallLifecycle/v1, cycle 16.1).
    doc["lifecycle"] = _lc.receipt_block(doc)
    return doc


def _receipt(operation: str, scope: str, target: Path, *,
             status: str, checks: list[dict[str, Any]],
             managed_files: list[str] | None = None,
             extra: dict[str, Any] | None = None) -> dict[str, Any]:
    doc = {
        "schema": kit.SCHEMA_RECEIPT, "forge_id": FORGE_ID,
        "operation": operation, "scope": scope,
        "target_root": str(target), "managed_files": managed_files or [],
        "checks": checks,
        "verification": {"status": _verification_status(checks)},
        "status": status, "created_at": kit._utc_now(),
        "created_by": f"platformforge/{__version__}",
    }
    if extra:
        doc.update(extra)
    # ``receipt_id`` is required by ``forge/InstallReceipt/v1`` — a digest
    # over the operation's evidence, matching the canonical installkit
    # semantics: install/repair bind ``{f: files, m: markers}``; uninstall
    # binds ``{r: removed, k: kept}``.
    if doc["operation"] == "uninstall":
        evidence = {"r": doc.get("removed") or [], "k": doc.get("kept") or []}
    else:
        evidence = {"f": doc.get("managed_files") or [],
                    "m": doc.get("managed_markers") or []}
    doc["receipt_id"] = f"sha256:{kit._sha(kit._json_bytes(evidence))}"
    # Derived ``forge/InstallLifecycle/v1`` view — additive; older parsers
    # keep working (contract §2). Computed after ``extra`` so batch
    # ``forges`` rows inform partially_applied.
    doc["lifecycle"] = _lc.receipt_block(doc)
    return doc


def _planned_files(plan: Any, assets: dict[str, bytes]) -> list[dict[str, Any]]:
    """Dry-run plan evidence in the contract shape — ``{path, kind,
    action, sha256}`` dicts (the-forge's ``_collect_forge_plan`` reads
    exactly this for cross-forge conflict detection; bare strings make
    it blind). Actions: create / update / conflict (user-modified managed
    path — still a claim, reported not written)."""
    out: list[dict[str, Any]] = []

    def _entry(rel: str, action: str) -> dict[str, Any]:
        return {
            "path": rel,
            "kind": kit._asset_kind(rel),
            "action": action,
            "sha256": kit._sha(assets[rel]),
        }

    for rel in sorted(plan.creates):
        out.append(_entry(rel, "create"))
    for rel in sorted(plan.managed_updates + plan.identical):
        out.append(_entry(rel, "update"))
    for rel in sorted(plan.conflicts):
        out.append(_entry(rel, "conflict"))
    return out


def install(*, scope: str = "project", root: Path | None = None,
            host: str = "all", profile: str = "recommended",
            yes: bool = False, dry_run: bool = False,
            components: tuple[str, ...] | None = None,
            gateway_profile: str = "balanced") -> dict[str, Any]:
    """``platformforge install`` — governed apply over ``apply_install``."""
    from platformforge.distribution.service import apply_install, plan_install

    _profile(profile)  # validates; native dist profile stays "agentic"
    _gateway_profile(gateway_profile)
    # install-2.1: the REQUESTED profile drives the component options (was
    # hardcoded "recommended") and the effective asset kinds — declared via
    # PROFILE_COMPONENTS when no explicit --components selection exists.
    try:
        opts = kit.component_options(profile, components)
    except kit.InstallError as exc:
        # Normalize to the service refusal type — the CLI catches
        # InstallRefusal; a raw InstallError would escape as a traceback.
        raise InstallRefusal(exc.kind, exc.detail) from exc
    if components is None:
        opts["asset_kinds"] = list(PROFILE_COMPONENTS[profile])
    opts["execution_profile"] = gateway_profile
    native_hosts = _hosts(host)
    target = _resolve(scope, root)
    state = target / ".platformforge"
    if dry_run:
        plan, _manifest, assets = plan_install(
            target, "agentic", native_hosts,
            asset_kinds=opts["asset_kinds"])
        return _receipt(
            "install", scope, target, status="planned",
            checks=[{"id": "plan", "status": "UNVERIFIED",
                     "detail": "dry-run — nothing written"}],
            extra={"dry_run": True,
                   "components": opts or None,
                   "gateway_profile": gateway_profile,
                   "planned_files": _planned_files(plan, assets),
                   "conflicts": plan.conflicts})
    if not yes:
        raise InstallRefusal(
            kit.E_NOTAPPROVED,
            "install requires --yes or --dry-run; the plan is the contract")
    with kit.acquire_lock(state):
        out = apply_install(target, "agentic", native_hosts,
                            asset_kinds=opts["asset_kinds"])
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
    # Fail-closed (install-2.1): verification is computed over ALL checks —
    # including the mcp-json/context-registry post-checks appended above —
    # and a BLOCKED/FAIL post-check flips status to failed.
    doc = _finalize_verification(doc)
    # Persist the contract receipt — emitted JSON alone is not auditable
    # (E2E F2): siblings write ``forge/InstallReceipt/v1`` under
    # ``<state>/receipts/``; ``_write_receipt`` re-derives lifecycle at
    # write time, after final status.
    kit._write_receipt(state, doc)
    if doc["status"] == "completed" and scope != "user":
        # Re-assert the account manifest so the-forge discovers the
        # declared install surface without a bootstrap re-run. User scope
        # installs assets under ~ — not a project runtime.
        _register(target)
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
        doc = {
            "schema": kit.SCHEMA_HEALTH, "forge_id": FORGE_ID,
            "status": "unverified", "target_root": str(target),
            "checks": [{"id": "receipt", "status": "UNVERIFIED",
                        "detail": "no install receipt"}],
            "checked_at": kit._utc_now(),
            "repair_hint": "platformforge install --yes",
        }
        doc["lifecycle"] = _lc.health_block(doc)
        return doc
    from platformforge.distribution.service import doctor as dist_doctor

    doc = dist_doctor(target)
    healthy = doc.get("state") == "healthy"
    drifted = bool(doc.get("drift") or doc.get("missing"))
    out = {
        "schema": kit.SCHEMA_HEALTH, "forge_id": FORGE_ID,
        "status": "healthy" if healthy else "degraded",
        "target_root": str(target),
        "checks": [{"id": f"pf:{k}", "status": "PASS" if v else "FAIL",
                    "detail": str(v)} for k, v in doc.get("checks", {}).items()],
        "distribution": doc,
        "checked_at": kit._utc_now(),
        "repair_hint": "platformforge install repair" if drifted else None,
    }
    out["lifecycle"] = _lc.health_block(out)
    return out


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
    out = {
        "schema": kit.SCHEMA_HEALTH, "forge_id": FORGE_ID,
        "status": "degraded" if failed else (
            "healthy" if doc.get("state") == "healthy" else "unverified"),
        "target_root": str(target), "checks": checks,
        "distribution": doc,
        "checked_at": kit._utc_now(),
        "repair_hint": "platformforge install repair" if failed else None,
    }
    out["lifecycle"] = _lc.health_block(out)
    return out


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
        # Replan with the SAME component selection the install recorded —
        # an absent `asset_kinds` (pre-selection installs) means the full
        # set, never a guess.
        stored_opts = kit.load_components(state)
        stored_kinds = stored_opts.get("asset_kinds")
        plan, _manifest, assets = plan_install(
            target, "agentic", hosts, asset_kinds=stored_kinds)
        restored: list[str] = []
        if not plan.conflicts:
            out = apply_install(target, "agentic", hosts,
                                asset_kinds=stored_kinds)
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
        # Registry de contexto (recuperacao §9.2): redo de journal de
        # transacao, reclaim de lock velho, rebuild de registry+ROUTING.md.
        try:
            out_ctx = fctx.repair_context(target)
            rec = out_ctx.get("recovered")
            checks.append({
                "id": "context-registry",
                "status": "PASS",
                "detail": (
                    f"{out_ctx['status']} "
                    f"({len(out_ctx['written'])} writes)"
                    + (f"; recovered {rec['op']}:{rec['forge_id']}" if rec else "")
                    + ("; stale lock reclaimed" if out_ctx.get("lock_recovered") else "")
                ),
            })
        except fctx.ContextError as exc:
            checks.append({
                "id": "context-registry",
                "status": "BLOCKED",
                "detail": f"{exc.kind}: {exc.detail}",
            })
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
    if _mcp_enabled(stored_opts) and _mcp_current(target) != _mcp_entry():
        checks.append(_mcp_set_project(target))
    # Modified managed files are user content by the platform-forge
    # ownership contract — preserved, never force-rewritten. Fail-closed:
    # a BLOCKED post-check (mcp-json/context-registry/consumer-docs) flips
    # status + verification, never a silent completed+PASS.
    doc = _finalize_verification(_receipt(
        "repair", scope, target,
        status="completed" if not remaining else "failed",
        checks=checks,
        extra={"repaired": [r for r in restored if r not in remaining],
               "kept": kept}))
    kit._write_receipt(state, doc)
    return doc


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
            checks += _unregister_context(target)
        checks.append(_mcp_unset_project(target))
        return _receipt("uninstall", scope, target,
                        status="failed" if any(c.get("status") == "BLOCKED" for c in checks)
                        else "completed",
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
        checks += _unregister_context(target)
    checks.append(_mcp_unset_project(target))
    doc = _receipt(
        "uninstall", scope, target,
        status="failed" if any(c.get("status") == "BLOCKED" for c in checks) else "completed",
        checks=checks,
        extra={"removed": removed,
               "kept": out.get("preserved_modified", [])})
    kit._write_receipt(state, doc)
    return doc


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
    doc = _receipt(
        "update", "user", Path.home(),
        status="completed" if proc.returncode == 0 else "failed",
        checks=[{"id": "pip",
                 "status": "PASS" if proc.returncode == 0 else "FAIL",
                 "detail": (proc.stdout or proc.stderr)[-300:]}])
    kit._write_receipt(Path.home() / ".platformforge", doc)
    return doc


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


def _bundled_json(name: str) -> dict[str, Any] | None:
    for cand in (_PKG_DIR / "data" / name, _REPO_DIR / name):
        data = kit._load_json(cand, None)
        if isinstance(data, dict):
            return data
    return None


def _installation_manifest() -> dict[str, Any]:
    path = kit.installations_dir() / f"{FORGE_ID}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _register(target: Path) -> None:
    """Re-assert ``~/.forge/installations/platform-forge.json`` after a
    project/workspace install (install-2.1, sibling parity): when the
    bootstrap already wrote the manifest the installed runtime stays
    authoritative — only the declared install fields are refreshed;
    otherwise a minimal manifest points at the project state."""
    existing = _installation_manifest()
    doc = dict(existing) if existing else {}
    doc.update(
        {
            "schema": kit.SCHEMA_MANIFEST,
            "forge_id": FORGE_ID,
            "package": "platformforge",
            "distribution": "platformforge",
            "cli": {
                "name": "platformforge",
                "version_cmd": ["platformforge", "--version"],
            },
            "version": __version__,
            "updated_at": kit._utc_now(),
            "installed_at": doc.get("installed_at", kit._utc_now()),
            "installed_by": doc.get(
                "installed_by",
                {"agent": "platformforge-cli", "version": __version__},
            ),
            "source": doc.get(
                "source", {"kind": "project-install", "path": str(target)}
            ),
        }
    )
    doc.setdefault("install_root", str(kit.installs_root() / FORGE_ID))
    doc.setdefault(
        "mcp",
        {
            "server_name": "platformforge",
            "command": ["platformforge-mcp"],
            "verify_tool": "platformforge_inspect",
            "verified": False,
        },
    )
    doc.update(_declared_install_fields())
    kit.register_installation(doc)


def _declared_install_fields() -> dict[str, Any]:
    """The install-2.1 declarations of THIS forge's ``forge.json`` —
    copied verbatim into the registered manifest, never fabricated
    (mirrors the ``forge_bootstrap`` register step):

    - ``installation_kind``: ``content``|``service``|``control-tool`` —
      the class the consolidated plan uses for stable ordering.
    - ``install``: the declared surface (operations/flags/hosts/scopes/
      profiles/approval) — the orchestrator's argv builder only sends
      what is declared.
    - ``depends_on``: forge_ids that must install first — declared even
      when empty (``[]``): the consolidated plan reads the key's
      presence as an explicit declaration, not missing data.
    """
    cfg = _bundled_json("forge.json")
    if not cfg:
        return {}
    doc: dict[str, Any] = {}
    if cfg.get("installation_kind"):
        kind = str(cfg["installation_kind"])
        if kind not in kit.INSTALLATION_KINDS:
            raise InstallRefusal(
                kit.E_UNSUPPORTED,
                f"forge.json installation_kind {kind!r} — expected "
                f"{kit.INSTALLATION_KINDS}",
            )
        doc["installation_kind"] = kind
    if cfg.get("install"):
        doc["install"] = dict(cfg["install"])
    if "depends_on" in cfg:
        doc["depends_on"] = [str(d) for d in cfg["depends_on"]]
    return doc


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

    forge_json = _bundled_json("forge.json")
    agentic = _bundled_json("forge.agentic.json")

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
    # §7.1 (lf-0038): a classificacao NAO vem do varrimento de `evals/` —
    # ela e a tabela declarada de `platformforge.evals.taxonomy`, que cobre
    # as 4 categorias do enum EVAL_KINDS (o corpus evals/cases e dividido
    # por `type`) e marca as suites seladas. Suites novas entram na tabela;
    # `evals describe <id>` e o command que o manifesto publica.
    from platformforge.evals import taxonomy as _evals_taxonomy

    eval_suites = _evals_taxonomy.manifest_suites("platformforge")

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
        kind="specialist",
        domains=_PF_DOMAINS,
        skills=skills,
        coordinators=coordinators,
        agents=agent_ids,
        rule_areas=rule_areas,
        knowledge_providers=providers,
        eval_suites=eval_suites,
        # As mesmas seis capabilities que `build_manifest` montaria por
        # default — declaradas porque `evals` ganha `detail`: o resumo
        # §7.1 das categorias + a postura §7.3.
        capabilities={
            "skills": fctx._capability_doc(
                bool(skills), discovery="workspace-file", count=len(skills)
            ),
            "agents": fctx._capability_doc(
                bool(agent_ids or coordinators),
                discovery="workspace-file",
                count=len(agent_ids) + len(coordinators),
            ),
            "knowledge": fctx._capability_doc(
                bool(providers), discovery="native-runtime", count=len(providers)
            ),
            "rules": fctx._capability_doc(
                bool(rule_areas), discovery="native-runtime", count=len(rule_areas)
            ),
            "evals": fctx._capability_doc(
                bool(eval_suites),
                discovery="cli",
                count=len(eval_suites),
                detail=_evals_taxonomy.capability_detail(),
            ),
            "protocols": fctx._capability_doc(True, discovery="bundled", count=3),
        },
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
            # §7.2 (lf-0038): evals.list/describe/run/result +
            # verification.plan/run. `discovery.ops` e vocabulario fechado
            # do §6.2 — os ops do §7.2 entram como commands nomeados.
            *discovery_ops.eval_commands(),
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
        # Uma UNICA transacao (install-2.0 §9.2): manifesto + entrada no
        # registry + ROUTING.md + consumer docs sob um lock, com backup,
        # verify e rollback — nunca registry-orfao de docs nem docs-orfaos
        # de registry.
        out = fctx.install_transaction(
            target, manifest, owner=FORGE_ID, legacy_tags=_LEGACY_DOC_TAGS
        )
        receipt.setdefault("checks", []).append(
            {
                "id": "context-registry",
                "status": "PASS",
                "detail": f".forge/context {out['status']} "
                f"({len(out['written'])} writes)",
            }
        )
        docs = out["docs"]
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
            {"id": "context-registry", "status": "BLOCKED",
             "detail": f"{exc.kind}: {exc.detail}"}
        )
        # BLOCKED num componente mandatório não sai exit 0 — os assets
        # foram escritos mas o contrato install-2.0 falhou.
        receipt["status"] = "failed"


def _unregister_context(target: Path) -> list[dict[str, Any]]:
    """Remove manifesto/entry/blocos `forge:*` deste forge numa UNICA
    transacao (§9.2) — só artifacts próprios: nosso capability file, nossa
    entrada no registry, nossos blocos; docs compartilhados regeneram
    para os sobreviventes."""
    try:
        out = fctx.uninstall_transaction(
            target, FORGE_ID, owner=FORGE_ID, legacy_tags=_LEGACY_DOC_TAGS
        )
        docs = out["docs"]
        return [
            {
                "id": "context-registry",
                "status": "PASS",
                "detail": f".forge/context {out['status']}",
            },
            {
                "id": "consumer-docs",
                "status": "PASS",
                "detail": f"{docs['status']}: {len(docs['written'])} changed",
            },
        ]
    except fctx.ContextError as exc:
        return [
            {
                "id": "context-registry",
                "status": "BLOCKED",
                "detail": f"{exc.kind}: {exc.detail}",
            }
        ]


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


def _mcp_entry() -> dict[str, Any]:
    """Managed ``.mcp.json`` entry — PATH-independent argv (§9.3).

    Resolves through the installkit (declared absolute argv → manifest
    shim/sibling script → entry-point module), so hosts never depend on
    the installer's PATH."""
    ctx = kit.InstallContext(
        spec=_spec(), scope="project", root=Path.cwd(),
        state_dir=Path.cwd(), profile="", hosts=())
    argv = kit._mcp_argv_resolved(ctx) or _spec().mcp_command
    return {"command": argv[0], "args": list(argv[1:])}


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
    new = kit.mcp_set(cur, _MCP_NAME, _mcp_entry(), FORGE_ID)
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
