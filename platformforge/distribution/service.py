"""Plan-first, ownership-aware portable install lifecycle."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
from typing import Iterable

from platformforge import __version__
from platformforge.agents.mirrors import expected as expected_agent_mirrors
from platformforge.distribution.models import (
    DistributionManifest, InstallPlan, InstallReceipt, ManagedAsset,
)
from platformforge.workspace.service import ensure_workspace
from platformforge.resources import data_path

PF_DIR = ".platformforge"
INSTALL_RECEIPT = "install-receipt.json"
DIST_MANIFEST = "distribution-manifest.json"
HOSTS = ("agents", "claude", "codex", "devin")

def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def _safe_target(root: Path, rel: str) -> Path:
    if Path(rel).is_absolute() or ".." in Path(rel).parts:
        raise ValueError("PF-DIST-PATH-ESCAPE")
    root = root.resolve()
    dest = (root / rel).resolve()
    if dest != root and root not in dest.parents:
        raise ValueError("PF-DIST-PATH-ESCAPE")
    return dest

def _host_prefix(host: str) -> str:
    return {"agents": ".agents/agents/", "claude": ".claude/agents/",
            "codex": ".codex/agents/", "devin": ".devin/agents/"}[host]

def portable_assets(hosts: Iterable[str]) -> dict[str, bytes]:
    hosts = tuple(dict.fromkeys(hosts))
    bad = set(hosts) - set(HOSTS)
    if bad:
        raise ValueError("PF-DIST-UNKNOWN-HOST:" + ",".join(sorted(bad)))
    rendered = expected_agent_mirrors(Path("."))
    out: dict[str, bytes] = {}
    prefixes = tuple(_host_prefix(h) for h in hosts)
    for rel, text in rendered.items():
        if rel.startswith(prefixes):
            out[rel] = text.encode()
    # Portable domain skills are package data. Codex consumes the generic
    # .agents skill surface alongside .codex/agents; Claude/Devin receive
    # their native skill directories. One canonical skill body is copied.
    skill_root = data_path("portable_skills")
    if skill_root.is_dir():
        for skill_dir in sorted(skill_root.iterdir()):
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.is_file():
                continue
            body = skill_file.read_bytes()
            if "agents" in hosts or "codex" in hosts:
                out[f".agents/skills/{skill_dir.name}/SKILL.md"] = body
            if "claude" in hosts:
                out[f".claude/skills/{skill_dir.name}/SKILL.md"] = body
            if "devin" in hosts:
                out[f".devin/skills/{skill_dir.name}/SKILL.md"] = body

    # Workspace-local MCP hint: never edits global host config.
    out[f"{PF_DIR}/mcp.json"] = json.dumps({
        "schema": "platformforge/mcp-bootstrap/v1",
        "command": ["platformforge-mcp"],
        "scope": "workspace-local",
    }, indent=2, sort_keys=True).encode() + b"\n"
    return out

def _distribution(profile: str, hosts: list[str], assets: dict[str, bytes],
                  source_sha: str = "") -> DistributionManifest:
    records = [ManagedAsset(path=p, sha256=_sha(b),
                            kind="host-mirror" if "/agents/" in p else "config")
               for p, b in sorted(assets.items())]
    semantic = json.dumps({
        "version": __version__, "profile": profile, "hosts": hosts,
        "assets": [(x.path, x.sha256) for x in records],
    }, sort_keys=True).encode()
    return DistributionManifest(
        distribution_id="sha256:" + _sha(semantic),
        platformforge_version=__version__,
        source_sha=source_sha,
        profile=profile,
        hosts=hosts,
        capabilities=["platform.inspect", "platform.graph", "platform.judge",
                      "platform.route", "platform.mcp"],
        assets=records,
        offline=True,
    )

def plan_install(target: str | Path, profile: str = "agentic",
                 hosts: list[str] | None = None) -> tuple[InstallPlan, DistributionManifest, dict[str, bytes]]:
    root = Path(target).resolve()
    hosts = hosts or ["agents"]
    assets = portable_assets(hosts)
    manifest = _distribution(profile, hosts, assets)
    receipt_path = root / PF_DIR / INSTALL_RECEIPT
    old = {}
    if receipt_path.is_file():
        try:
            old = json.loads(receipt_path.read_text()).get("files", {})
        except (OSError, ValueError):
            old = {}
    creates, identical, managed_updates, conflicts = [], [], [], []
    for rel, data in sorted(assets.items()):
        dest = _safe_target(root, rel)
        want = _sha(data)
        if not dest.exists():
            creates.append(rel)
            continue
        current = _sha(dest.read_bytes())
        if current == want:
            identical.append(rel)
        elif old.get(rel) == current:
            managed_updates.append(rel)
        else:
            conflicts.append(rel)
    return InstallPlan(str(root), profile, hosts, creates, identical,
                       managed_updates, conflicts, network_required=False), manifest, assets

def apply_install(target: str | Path, profile: str = "agentic",
                  hosts: list[str] | None = None, dry_run: bool = False) -> dict:
    plan, manifest, assets = plan_install(target, profile, hosts)
    if dry_run:
        return {"plan": plan.to_dict(), "distribution": manifest.to_dict()}
    if not plan.safe:
        return {"refusal": "PF-DIST-CONFLICT", "conflicts": plan.conflicts,
                "unlock": "preserve/rename modified files or choose another host"}
    root = Path(target).resolve()
    staged: list[tuple[Path, Path]] = []
    try:
        for rel in plan.creates + plan.managed_updates:
            dest = _safe_target(root, rel)
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_name(dest.name + ".platformforge-stage")
            tmp.write_bytes(assets[rel])
            if _sha(tmp.read_bytes()) != _sha(assets[rel]):
                raise OSError("PF-DIST-STAGE-HASH")
            staged.append((tmp, dest))
        for tmp, dest in staged:
            os.replace(tmp, dest)
        ws = ensure_workspace(root, profile=profile, hosts=plan.hosts)
        pf = root / PF_DIR
        manifest_path = pf / DIST_MANIFEST
        manifest_path.write_text(json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n")
        files = {rel: _sha(_safe_target(root, rel).read_bytes()) for rel in assets}
        receipt = InstallReceipt(
            manifest.distribution_id, __version__, manifest.source_sha,
            str(root), profile, plan.hosts, files,
        )
        (pf / INSTALL_RECEIPT).write_text(json.dumps(receipt.to_dict(), indent=2, sort_keys=True) + "\n")
        return {"status": "committed", "plan": plan.to_dict(),
                "workspace": ws.to_dict(), "receipt": receipt.to_dict()}
    except Exception:
        for tmp, _ in staged:
            tmp.unlink(missing_ok=True)
        raise

def uninstall(target: str | Path, purge: bool = False) -> dict:
    root = Path(target).resolve()
    receipt_path = root / PF_DIR / INSTALL_RECEIPT
    if not receipt_path.is_file():
        return {"refusal": "PF-DIST-NOT-INSTALLED"}
    rec = json.loads(receipt_path.read_text())
    removed, preserved = [], []
    for rel, installed_hash in rec.get("files", {}).items():
        dest = _safe_target(root, rel)
        if not dest.exists():
            continue
        if _sha(dest.read_bytes()) == installed_hash:
            dest.unlink()
            removed.append(rel)
        else:
            preserved.append(rel)
    for name in (DIST_MANIFEST, INSTALL_RECEIPT):
        (root / PF_DIR / name).unlink(missing_ok=True)
    if purge:
        ws = root / PF_DIR / "workspace.json"
        ws.unlink(missing_ok=True)
    return {"status": "uninstalled", "removed": removed,
            "preserved_modified": preserved, "purged": purge}

def upgrade(target: str | Path, profile: str | None = None,
            hosts: list[str] | None = None, dry_run: bool = False) -> dict:
    root = Path(target).resolve()
    recp = root / PF_DIR / INSTALL_RECEIPT
    if not recp.is_file():
        return {"refusal": "PF-DIST-NOT-INSTALLED",
                "unlock": "platformforge install ."}
    old = json.loads(recp.read_text())
    profile = profile or old.get("profile", "agentic")
    hosts = hosts or list(old.get("hosts", ["agents"]))
    return apply_install(root, profile=profile, hosts=hosts, dry_run=dry_run)

def doctor(target: str | Path) -> dict:
    root = Path(target).resolve()
    pf = root / PF_DIR
    recp, manp = pf / INSTALL_RECEIPT, pf / DIST_MANIFEST
    checks = {"workspace": (pf / "workspace.json").is_file(),
              "receipt": recp.is_file(), "manifest": manp.is_file()}
    drift, missing = [], []
    if recp.is_file():
        rec = json.loads(recp.read_text())
        for rel, expected_hash in rec.get("files", {}).items():
            p = _safe_target(root, rel)
            if not p.is_file():
                missing.append(rel)
            elif _sha(p.read_bytes()) != expected_hash:
                drift.append(rel)
    checks["assets"] = not missing and not drift
    state = "healthy" if all(checks.values()) else "warning"
    return {"state": state, "checks": checks, "missing": missing,
            "drift": drift, "workspace_local": True}
