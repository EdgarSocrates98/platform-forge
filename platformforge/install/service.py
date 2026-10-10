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

from platformforge import __version__
from platformforge import _installkit as kit

FORGE_ID = "platform-forge"
PROFILES: tuple[str, ...] = ("minimal", "recommended", "full")
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
    # workspace: walk up for .platformforge/workspace.json else refuse
    t = Path(root).resolve() if root else Path.cwd().resolve()
    for cand in (t, *t.parents):
        if (cand / ".platformforge" / "workspace.json").is_file():
            return cand
    raise InstallRefusal(
        kit.E_NOTINSTALLED,
        "no .platformforge/workspace.json in ancestry — "
        "platformforge workspace init first")


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
            components: tuple[str, ...] | None = None) -> dict[str, Any]:
    """``platformforge install`` — governed apply over ``apply_install``."""
    from platformforge.distribution.service import apply_install, plan_install

    _profile(profile)  # validates; native profile is always "agentic"
    opts = kit.component_options("recommended", components)
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
    return _receipt(
        "install", scope, target, status="completed",
        checks=[{"id": "apply", "status": "PASS",
                 "detail": f"{len(receipt.get('files', {}))} managed files"}],
        managed_files=sorted(receipt.get("files", {})),
        extra={"plan": out.get("plan"), "profile": profile,
               "components": opts or None})


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
    # Modified managed files are user content by the platform-forge
    # ownership contract — preserved, never force-rewritten.
    return _receipt(
        "repair", scope, target,
        status="completed" if not remaining else "failed",
        checks=[{"id": "repair",
                 "status": "PASS" if not remaining else "FAIL",
                 "detail": f"{len(missing)} missing restored, "
                           f"{len(remaining)} remaining; "
                           f"{len(kept)} user-modified preserved"}],
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
        return _receipt("uninstall", scope, target, status="completed",
                        checks=[{"id": "uninstall", "status": "PASS",
                                 "detail": "0 removed — nothing installed"}],
                        extra={"removed": [], "kept": []})
    with kit.acquire_lock(state):
        out = dist_uninstall(target, purge=purge)
    if "refusal" in out:
        return _receipt("uninstall", scope, target, status="failed",
                        checks=[{"id": "uninstall", "status": "FAIL",
                                 "detail": out["refusal"]}])
    removed = out.get("removed", [])
    kit._prune_empty_dirs(target, removed)
    return _receipt(
        "uninstall", scope, target, status="completed",
        checks=[{"id": "uninstall", "status": "PASS",
                 "detail": f"{len(removed)} removed, "
                           f"{len(out.get('preserved_modified', []))} preserved"}],
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
