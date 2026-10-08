"""Event ledger — append-only journal of graph/observation events.

§97–99 — daily JSONL journals under `.platformforge/events/`; compaction
writes a snapshot marker and prunes old segments; retention is explicit
and never deletes events whose fact/graph/artifact ids are still
referenced by incidents, findings, or receipts.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

EVENTS_DIR = ".platformforge/events"
EVENT_KINDS = ("observation", "drift", "change", "identity", "incident",
               "snapshot", "watch")


def _day(ts: str) -> str:
    return (ts or "")[:10] or "undated"


def utcnow() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class EventLedger:
    """Append-only, deterministic, partition-per-day journal."""

    def __init__(self, root: str | Path):
        self.dir = Path(root) / EVENTS_DIR

    def _segment(self, ts: str) -> Path:
        return self.dir / f"{_day(ts)}.jsonl"

    def append(self, event: dict[str, Any]) -> dict[str, Any]:
        kind = event.get("kind")
        if kind not in EVENT_KINDS:
            raise ValueError(f"unknown event kind: {kind!r}")
        ev = dict(event)
        ev.setdefault("timestamp", utcnow())
        self.dir.mkdir(parents=True, exist_ok=True)
        with self._segment(ev["timestamp"]).open("a") as f:
            f.write(json.dumps(ev, sort_keys=True) + "\n")
        return ev

    def events(self, *, kind: str | None = None,
               since: str = "", until: str = "") -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        if not self.dir.exists():
            return out
        for p in sorted(self.dir.glob("*.jsonl")):
            for line in p.read_text().splitlines():
                if not line.strip():
                    continue
                ev = json.loads(line)
                ts = ev.get("timestamp", "")
                if kind and ev.get("kind") != kind:
                    continue
                if since and ts < since:
                    continue
                if until and ts > until:
                    continue
                out.append(ev)
        return out

    def compact(self, *, snapshot_hash: str,
                keep_after: str = "") -> dict[str, Any]:
        """Write a compaction marker; segments fully older than
        `keep_after` (ISO date) are removed. Returns the marker."""
        removed = []
        for p in sorted(self.dir.glob("*.jsonl")):
            if keep_after and p.stem < keep_after:
                p.unlink()
                removed.append(p.name)
        marker = self.append({
            "kind": "snapshot", "snapshot_hash": snapshot_hash,
            "compacted_segments": sorted(removed)})
        return {"marker": marker, "removed_segments": sorted(removed)}

    def prune(self, *, keep_days: int,
              protected_ids: set[str] | None = None) -> dict[str, Any]:
        """Retention: drop segments older than keep_days. Events
        referencing protected ids are copied forward into the newest
        surviving segment (§99 — never delete cited evidence)."""
        protected_ids = protected_ids or set()
        cutoff = time.strftime(
            "%Y-%m-%d", time.gmtime(time.time() - keep_days * 86400))
        kept, dropped, rescued = 0, 0, 0
        survivors: list[dict[str, Any]] = []
        for p in sorted(self.dir.glob("*.jsonl")):
            if p.stem >= cutoff:
                kept += 1
                continue
            for line in p.read_text().splitlines():
                if not line.strip():
                    continue
                ev = json.loads(line)
                refs = set(ev.get("fact_ids", [])) | set(
                    ev.get("artifact_hashes", []))
                if ev.get("graph_hash"):
                    refs.add(ev["graph_hash"])
                if refs & protected_ids:
                    survivors.append(ev)
                    rescued += 1
            p.unlink()
            dropped += 1
        if survivors:
            seg = self.dir / f"{cutoff}.rescued.jsonl"
            with seg.open("a") as f:
                for ev in survivors:
                    f.write(json.dumps(ev, sort_keys=True) + "\n")
        return {"segments_kept": kept, "segments_dropped": dropped,
                "events_rescued": rescued}
