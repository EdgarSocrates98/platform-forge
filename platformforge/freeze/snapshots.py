"""§7/§196 — contract snapshots + breaking-change detection.

Snapshot = {name: {id: sha256}} over contracts/, CLI verbs, MCP tools,
capabilities, agent roster. `check` diffs current vs stored and reports
drift as added/removed/changed. Knowledge version bumps are allowlisted.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

SNAP_DIR = Path("docs/freeze/snapshots")

# changes in these snapshot families are informational, not breaking
ALLOWLIST = ("knowledge",)


def _h(s: str | bytes) -> str:
    return hashlib.sha256(s if isinstance(s, bytes) else s.encode()).hexdigest()


def build_snapshots(repo: str | Path = ".") -> dict[str, Any]:
    repo = Path(repo)
    snaps: dict[str, Any] = {}

    # schemas — hash of each file's content
    snaps["schemas"] = {
        p.name: _h(p.read_bytes())
        for p in sorted((repo / "contracts").glob("*.schema.json"))
    }

    from platformforge.cli.main import build_parser
    p = build_parser()
    sub = next(a for a in p._actions if hasattr(a, "choices") and a.choices)
    snaps["cli"] = {v: _h(v) for v in sorted(sub.choices)}

    from platformforge.mcp.registry import tool_descriptors
    snaps["mcp"] = {t["name"]: _h(t["name"]) for t in tool_descriptors()}

    from platformforge.mcp.registry import CAPABILITIES
    snaps["capabilities"] = {
        c.name: _h(json.dumps(c.contract(), sort_keys=True, default=str))
        for c in CAPABILITIES.values()
    }

    from platformforge.agents.roster import AGENTS
    snaps["agents"] = {
        n: _h(json.dumps(
            {f: getattr(a, f) for f in a.__dataclass_fields__
             if isinstance(getattr(a, f), (str, int, bool, list, tuple))
             } | {"role": a.role}, sort_keys=True, default=str))
        for n, a in sorted(AGENTS.items())
    }

    # knowledge packs — allowlisted (version bumps expected, not breaking)
    kroot = repo / "knowledge"
    snaps["knowledge"] = {
        str(p.relative_to(kroot)): _h(p.read_bytes())
        for p in sorted(kroot.rglob("*.yaml")) + sorted(kroot.rglob("*.md"))
    } if kroot.exists() else {}

    return snaps


def write_snapshots(repo: str | Path = ".", out: str | Path = SNAP_DIR) -> Path:
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    sha = subprocess.run(["git", "rev-parse", "HEAD"], check=False,
                         capture_output=True, text=True).stdout.strip()
    for name, entries in build_snapshots(repo).items():
        (out / f"{name}.json").write_text(json.dumps(
            {"schema": "platformforge/freeze-snapshot/v1",
             "family": name, "sha": sha, "entries": entries},
            indent=2, sort_keys=True) + "\n")
    return out


def check_snapshots(repo: str | Path = ".", snap_dir: str | Path = SNAP_DIR
                    ) -> dict[str, Any]:
    """Returns {'breaking': [...], 'allowed': [...], 'missing': [...]} —
    breaking = changed/removed non-allowlisted entries."""
    snap_dir = Path(snap_dir)
    current = build_snapshots(repo)
    breaking: list[str] = []
    allowed: list[str] = []
    missing: list[str] = []
    for name, entries in current.items():
        f = snap_dir / f"{name}.json"
        if not f.exists():
            missing.append(name)
            continue
        old = json.loads(f.read_text())["entries"]
        for k, h in entries.items():
            tag = f"{name}:{k}"
            if k not in old:
                (allowed if name in ALLOWLIST else breaking).append(f"added {tag}")
            elif old[k] != h:
                (allowed if name in ALLOWLIST else breaking).append(f"changed {tag}")
        for k in old:
            if k not in entries:
                (allowed if name in ALLOWLIST else breaking).append(f"removed {name}:{k}")
    verdict = "pass" if not breaking else "fail"
    return {"schema": "platformforge/freeze-check/v1",
            "verdict": verdict, "breaking": breaking,
            "allowed": allowed, "missing": missing}
