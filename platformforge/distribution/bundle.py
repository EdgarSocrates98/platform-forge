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
