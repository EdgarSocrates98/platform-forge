"""Graph persistence: canonical JSON + content-addressed snapshots."""

from __future__ import annotations

import json
import time
from pathlib import Path

from platformforge.graph.model import Graph

GRAPH_DIR = ".platformforge/graph"


def save(graph: Graph, root: str | Path, name: str = "current") -> Path:
    d = Path(root) / GRAPH_DIR
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{name}.json"
    p.write_text(graph.to_json() + "\n")
    snap = d / "snapshots" / f"{graph.graph_hash}.json"
    if not snap.exists():
        snap.parent.mkdir(parents=True, exist_ok=True)
        snap.write_text(graph.to_json() + "\n")
    return p


def load(root: str | Path, name: str = "current") -> Graph:
    p = Path(root) / GRAPH_DIR / f"{name}.json"
    if not p.exists():
        raise FileNotFoundError(f"no graph named {name!r}")
    return Graph.from_dict(json.loads(p.read_text()))


def load_snapshot(root: str | Path, graph_hash: str) -> Graph:
    p = Path(root) / GRAPH_DIR / "snapshots" / f"{graph_hash}.json"
    if not p.exists():
        raise FileNotFoundError(f"no snapshot {graph_hash}")
    return Graph.from_dict(json.loads(p.read_text()))


def snapshots(root: str | Path) -> list[dict[str, str]]:
    d = Path(root) / GRAPH_DIR / "snapshots"
    if not d.exists():
        return []
    out = []
    for p in sorted(d.glob("*.json")):
        out.append({"graph_hash": p.stem,
                    "saved_at": time.strftime(
                        "%Y-%m-%dT%H:%M:%SZ",
                        time.gmtime(p.stat().st_mtime))})
    return out
