"""Temporal graph queries (§95).

Answers over persisted snapshots + the event ledger:
- "how was the graph at T1?"        → nearest snapshot ≤ T1
- "what changed between T1→T2?"     → snapshot diff (graph.diff)
- "when did this edge appear?"      → first event mentioning eid
- "when was X last observed?"       → last observation event for node
"""

from __future__ import annotations

from typing import Any

from platformforge.graph import persist
from platformforge.graph.events import EventLedger
from platformforge.graph.model import Edge


def snapshot_at(root, ts: str) -> dict[str, Any] | None:
    """The most recent snapshot whose timestamp ≤ ts."""
    best: dict[str, Any] | None = None
    for s in persist.snapshots(root):
        st = s.get("timestamp", "")
        if st and st <= ts and (best is None or st > best["timestamp"]):
            best = s
    return best


def graph_at(root, ts: str):
    s = snapshot_at(root, ts)
    if s is None:
        return None
    return persist.load_snapshot(root, s["graph_hash"])


def edge_first_seen(root, eid: str) -> str | None:
    ledger = EventLedger(root)
    seen = [
        ev.get("timestamp", "")
        for ev in ledger.events()
        if eid in (ev.get("edge_ids") or []) or ev.get("edge_id") == eid]
    return min(seen) if seen else None


def node_last_observed(root, node_id: str) -> str | None:
    ledger = EventLedger(root)
    seen = [
        ev.get("timestamp", "")
        for ev in ledger.events()
        if node_id in (ev.get("node_ids") or []) or ev.get("node_id") == node_id]
    return max(seen) if seen else None


def expire_stale_edges(graph, *, now: str,
                       max_age_s: float) -> list[str]:
    """§92 — observed edges whose temporal.last_seen is older than
    `max_age_s` relative to `now` are marked `temporal.expired=True`
    ("not recently observed") — never silently deleted; absence of
    traffic ≠ absence of dependency."""
    from datetime import datetime

    def _ts(s: str):
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    now_dt = _ts(now)
    expired: list[str] = []
    for eid, edge in list(graph.edges.items()):
        last = (edge.temporal or {}).get("last_seen")
        if edge.provenance != "observed" or not last:
            continue
        if (now_dt - _ts(last)).total_seconds() > max_age_s:
            t = dict(edge.temporal)
            t["expired"] = True
            graph.edges[eid] = Edge(
                edge.src, edge.dst, edge.kind, edge.provenance,
                edge.confidence, edge.source_fact_ids, edge.attrs,
                edge.evidence, t)
            expired.append(eid)
    return sorted(expired)
