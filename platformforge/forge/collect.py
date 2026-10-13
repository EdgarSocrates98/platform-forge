"""Sibling-Forge ingress — §82–83. Read-only: invokes a sibling forge's
own CLI if installed, or reads its emitted manifest/facts files.
Never shells out to providers; sibling forges are offline-first too."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from platformforge.models.base import stable_id

KNOWN_FORGES = {
    "api-forge": {"cli": "apiforge", "manifest_cmd": ["capability", "manifest"]},
    "spark-forge-aws": {"cli": "sparkforge-aws",
                        "manifest_cmd": ["capability", "manifest"]},
    "platform-forge": {"cli": "platformforge",
                       "manifest_cmd": ["forge", "manifest"]},
}


def discover(root: str | Path) -> dict[str, Any]:
    """Find sibling forge repos under a directory — marker: pyproject name
    or an AGENTS.md declaring the forge."""
    root = Path(root)
    found = []
    for d in sorted(root.iterdir()):
        if not d.is_dir():
            continue
        py = d / "pyproject.toml"
        if py.exists():
            head = py.read_text(errors="replace")[:2000]
            for fname in KNOWN_FORGES:
                if f'name = "{fname.replace("-", "")}"' in head or \
                        fname in head:
                    found.append({"forge": fname, "path": str(d),
                                  "marker": "pyproject"})
                    break
    return {"root": str(root), "forges": found}


def collect_manifest(forge_root: str | Path,
                     timeout: int = 30) -> dict[str, Any]:
    """Run the sibling's own capability manifest via its CLI if available;
    else refuse with the unlock path — we never guess a manifest."""
    root = Path(forge_root)
    py = root / "pyproject.toml"
    if not py.exists():
        return {"refusal": "platform.forge.unresolved",
                "detail": f"{root} is not a forge root (no pyproject.toml)",
                "unlock": "point --path at a forge repository"}
    cli = None
    for name, spec in KNOWN_FORGES.items():
        if name in py.read_text(errors="replace")[:2000]:
            cli = shutil.which(spec["cli"])
            if cli:
                r = subprocess.run([cli, *spec["manifest_cmd"], "--format",
                                    "json"],
                                   capture_output=True, text=True,
                                   timeout=timeout, check=False, cwd=root)
                if r.returncode == 0:
                    try:
                        manifest = json.loads(r.stdout)
                    except json.JSONDecodeError:
                        manifest = {"raw": r.stdout[:4000]}
                    return {"forge": name, "manifest": manifest,
                            "fact_id": stable_id("PF-FORG", name, str(root)),
                            "source": "cli"}
            return {"forge": name, "refusal": "platform.forge.cli_missing",
                    "detail": f"{spec['cli']} not on PATH",
                    "unlock": f"pip install -e {root}"}
    return {"refusal": "platform.forge.unknown",
            "detail": f"{root.name} is not a recognized sibling forge",
            "unlock": "extend KNOWN_FORGES with its CLI + manifest verb"}


def ingest_facts(facts_doc: dict[str, Any], forge: str) -> dict[str, Any]:
    """Wrap another forge's fact dicts — they stay tier-3+ evidence with a
    provenance marker; we never claim their evidence as ours."""
    facts = []
    for f in facts_doc.get("facts", []):
        f = dict(f)
        f.setdefault("attrs", {})["external_forge"] = forge
        f.setdefault("tier", 3)
        facts.append(f)
    return {"facts": facts, "count": len(facts), "forge": forge}
