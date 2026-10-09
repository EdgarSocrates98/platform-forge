"""Self-contained, relocatable portable bundles."""
from __future__ import annotations
import hashlib
import json
import shutil
from pathlib import Path

from platformforge.distribution.service import _distribution, portable_assets

def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def build_bundle(output: str | Path, profile: str = "agentic",
                 hosts: list[str] | None = None, offline: bool = True) -> dict:
    hosts = hosts or ["agents"]
    root = Path(output).resolve()
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    assets = portable_assets(hosts)
    manifest = _distribution(profile, hosts, assets)
    for rel, data in assets.items():
        p = root / "assets" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    (root / "manifest.json").write_text(json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n")
    lines = []
    for p in sorted((root / "assets").rglob("*")):
        if p.is_file():
            rel = p.relative_to(root)
            lines.append(f"{_sha(p.read_bytes())}  {rel.as_posix()}")
    (root / "MANIFEST.sha256").write_text("\n".join(lines) + "\n")
    return {"bundle": str(root), "distribution_id": manifest.distribution_id,
            "assets": len(assets), "offline": offline}

def verify_bundle(bundle: str | Path) -> dict:
    root = Path(bundle).resolve()
    mp, cp = root / "manifest.json", root / "MANIFEST.sha256"
    if not mp.is_file() or not cp.is_file():
        return {"valid": False, "refusal": "PF-DIST-BUNDLE-INCOMPLETE"}
    bad = []
    for line in cp.read_text().splitlines():
        if not line.strip():
            continue
        digest, rel = line.split("  ", 1)
        p = (root / rel).resolve()
        if root not in p.parents:
            bad.append(rel + ":path-escape")
        elif not p.is_file() or _sha(p.read_bytes()) != digest:
            bad.append(rel)
    return {"valid": not bad, "bad": bad,
            "refusal": None if not bad else "PF-DIST-HASH-MISMATCH"}


def install_bundle(bundle: str | Path, target: str | Path) -> dict:
    """Install a verified bundle without network access."""
    from platformforge.distribution.models import DistributionManifest, InstallReceipt, DIST_SCHEMA
    from platformforge.distribution.service import _safe_target, _sha, PF_DIR, INSTALL_RECEIPT, DIST_MANIFEST
    from platformforge.workspace.service import ensure_workspace
    import os

    root = Path(bundle).resolve()
    target = Path(target).resolve()
    verified = verify_bundle(root)
    if not verified["valid"]:
        return verified
    manifest = DistributionManifest.from_dict(json.loads((root / "manifest.json").read_text()))
    if manifest.schema != DIST_SCHEMA:
        return {"valid": False, "refusal": "PF-DIST-UNSUPPORTED-SCHEMA",
                "schema": manifest.schema}

    old = {}
    rp = target / PF_DIR / INSTALL_RECEIPT
    if rp.is_file():
        try:
            old = json.loads(rp.read_text()).get("files", {})
        except (OSError, ValueError):
            old = {}

    conflicts, writes = [], []
    for asset in manifest.assets:
        src = (root / "assets" / asset.path).resolve()
        if root not in src.parents or not src.is_file():
            return {"valid": False, "refusal": "PF-DIST-BUNDLE-INCOMPLETE",
                    "asset": asset.path}
        dest = _safe_target(target, asset.path)
        if dest.exists():
            cur = _sha(dest.read_bytes())
            if cur == asset.sha256:
                continue
            if old.get(asset.path) != cur:
                conflicts.append(asset.path)
                continue
        writes.append((src, dest))
    if conflicts:
        return {"refusal": "PF-DIST-CONFLICT", "conflicts": conflicts}

    staged = []
    try:
        for src, dest in writes:
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_name(dest.name + ".platformforge-stage")
            tmp.write_bytes(src.read_bytes())
            staged.append((tmp, dest))
        for tmp, dest in staged:
            os.replace(tmp, dest)
        ensure_workspace(target, profile=manifest.profile, hosts=manifest.hosts)
        pf = target / PF_DIR
        pf.mkdir(parents=True, exist_ok=True)
        (pf / DIST_MANIFEST).write_text(json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n")
        files = {a.path: a.sha256 for a in manifest.assets}
        receipt = InstallReceipt(
            manifest.distribution_id, manifest.platformforge_version,
            manifest.source_sha, str(target), manifest.profile,
            manifest.hosts, files,
        )
        (pf / INSTALL_RECEIPT).write_text(json.dumps(receipt.to_dict(), indent=2, sort_keys=True) + "\n")
        return {"status": "committed", "offline": True,
                "distribution_id": manifest.distribution_id,
                "files": len(files), "target": str(target)}
    except Exception:
        for tmp, _ in staged:
            tmp.unlink(missing_ok=True)
        raise
