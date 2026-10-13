"""Graph persistence: canonical JSON + content-addressed snapshots.

§6 — every snapshot carries an envelope: snapshot_id, timestamp, source,
source_type (desired|planned|observed|runtime), environment, workspace,
commit, provider, scope, graph_hash, fact_ids. Comparisons across types
(desired↔planned↔observed) use graph.diff.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from platformforge.graph.model import Graph

GRAPH_DIR = ".platformforge/graph"

SNAPSHOT_FIELDS = ("snapshot_id", "timestamp", "source", "source_type",
                   "environment", "workspace", "commit", "provider",
                   "scope", "graph_hash", "fact_ids")
SOURCE_TYPES = ("desired", "planned", "observed", "runtime")


def snapshot_meta(graph: Graph, *, source: str = "",
                  source_type: str = "desired", environment: str = "",
                  workspace: str = "", commit: str = "", provider: str = "",
                  scope: str = "", fact_ids: list[str] | None = None,
                  ) -> dict[str, Any]:
    if source_type not in SOURCE_TYPES:
        raise ValueError(f"source_type must be one of {SOURCE_TYPES}")
    all_fids = sorted({fid for n in graph.nodes.values()
                       for fid in getattr(n, "source_fact_ids", ())})
    return {
        "snapshot_id": f"gsnap-{graph.graph_hash[:16]}",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": source, "source_type": source_type,
        "environment": environment, "workspace": workspace,
        "commit": commit, "provider": provider, "scope": scope,
        "graph_hash": graph.graph_hash,
        "fact_ids": sorted(set(fact_ids or all_fids)),
    }


def save(graph: Graph, root: str | Path, name: str = "current",
         **meta_kwargs: Any) -> Path:
    d = Path(root) / GRAPH_DIR
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{name}.json"
    p.write_text(graph.to_json() + "\n")
    snap = d / "snapshots" / f"{graph.graph_hash}.json"
    meta = d / "snapshots" / f"{graph.graph_hash}.meta.json"
    if not snap.exists():
        snap.parent.mkdir(parents=True, exist_ok=True)
        snap.write_text(graph.to_json() + "\n")
        meta.write_text(json.dumps(snapshot_meta(graph, **meta_kwargs),
                                   indent=2, sort_keys=True) + "\n")
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


def snapshot_meta_of(root: str | Path, graph_hash: str) -> dict[str, Any]:
    p = Path(root) / GRAPH_DIR / "snapshots" / f"{graph_hash}.meta.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text())


def snapshots(root: str | Path) -> list[dict[str, Any]]:
    d = Path(root) / GRAPH_DIR / "snapshots"
    if not d.exists():
        return []
    out = []
    for p in sorted(d.glob("*.json")):
        if p.name.endswith(".meta.json"):
            continue
        entry: dict[str, Any] = {
            "graph_hash": p.stem,
            "saved_at": time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime(p.stat().st_mtime))}
        entry.update(snapshot_meta_of(root, p.stem))
        out.append(entry)
    return out
