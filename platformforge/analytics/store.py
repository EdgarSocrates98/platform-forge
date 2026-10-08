"""Cycle 5 Phase O — SQLite analytics store (§315–318).

Local, deterministic persistence for history events, fleet snapshots
and computed patterns. Same durability contract as GraphBackend:
offline-first, no network, retention-driven GC, and subject-level
deletion (right-to-forget, §321). Never stores secrets — callers pass
already-redacted event dicts; a payload containing a banned key is
refused rather than stored.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_BANNED_KEYS = {"secret", "password", "token", "api_key", "private_key",
                "credential", "authorization"}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    ts TEXT NOT NULL,
    subject TEXT NOT NULL,
    outcome TEXT NOT NULL,
    source TEXT NOT NULL,
    source_ref TEXT NOT NULL,
    attrs TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_events_ts ON events(ts);
CREATE INDEX IF NOT EXISTS ix_events_subj ON events(subject);
CREATE INDEX IF NOT EXISTS ix_events_kind ON events(kind);
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fleet_id TEXT NOT NULL,
    taken_at TEXT NOT NULL,
    doc TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern_id TEXT NOT NULL,
    window TEXT NOT NULL,
    computed_at TEXT NOT NULL,
    doc TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""

# §217 — schema versioning: opening a v1 store upgrades it through the
# declared migration chain. Migrations are additive, deterministic,
# and recorded — never a silent DDL change.
SCHEMA_VERSION = 2
_MIGRATIONS: dict[int, list[str]] = {
    2: [("CREATE INDEX IF NOT EXISTS ix_events_subj_kind "
       "ON events(subject, kind)")],
}


def _contains_banned(obj: Any, depth: int = 0) -> bool:
    if depth > 6:
        return False
    if isinstance(obj, dict):
        return any(str(k).lower() in _BANNED_KEYS or
                   _contains_banned(v, depth + 1)
                   for k, v in obj.items())
    if isinstance(obj, (list, tuple)):
        return any(_contains_banned(v, depth + 1) for v in obj)
    return False


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class AnalyticsStore:
    """SQLite-backed persistence for analytics (§315)."""

    def __init__(self, path: str | Path = ":memory:"):
        self.path = str(path)
        self._db = sqlite3.connect(self.path)
        self._db.executescript(_SCHEMA)
        self._migrate()

    def _migrate(self) -> None:
        """§217 — apply pending migrations in order, record the version."""
        row = self._db.execute(
            "SELECT value FROM meta WHERE key='schema_version'"
        ).fetchone()
        version = int(row[0]) if row else 1
        applied = []
        while version < SCHEMA_VERSION:
            version += 1
            for sql in _MIGRATIONS.get(version, []):
                self._db.execute(sql)
            applied.append(version)
        self._db.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES"
            "('schema_version', ?)", (str(SCHEMA_VERSION),))
        if applied:
            self._db.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES"
                "('migrations_applied', ?)", (",".join(map(str, applied)),))
        self._db.commit()

    def close(self) -> None:
        self._db.close()

    # -- events -----------------------------------------------------

    def put_event(self, kind: str, ts: str, subject: str,
                  outcome: str, source: str, attrs: dict[str, Any],
                  source_ref: str = "") -> dict[str, Any]:
        """§321 — refuse payloads that smell like secrets."""
        if _contains_banned(attrs):
            return {"refusal": "PF-ANALYTICS-SECRET",
                    "unlock": "redact attrs before storing — the "
                              "store never persists secrets"}
        self._db.execute(
            "INSERT INTO events(kind, ts, subject, outcome, source,"
            " source_ref, attrs) VALUES(?,?,?,?,?,?,?)",
            (kind, ts, subject, outcome, source, source_ref,
             json.dumps(attrs, sort_keys=True, default=str)))
        self._db.commit()
        return {"stored": True}

    def put_events(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        """Bulk insert — single commit; same secret-refusal contract."""
        refused = 0
        cur = self._db.cursor()
        for r in rows:
            if _contains_banned(r.get("attrs", {})):
                refused += 1
                continue
            cur.execute(
                "INSERT INTO events(kind, ts, subject, outcome, source,"
                " source_ref, attrs) VALUES(?,?,?,?,?,?,?)",
                (r["kind"], r["ts"], r.get("subject", ""),
                 r.get("outcome", ""), r.get("source", "bulk"),
                 r.get("source_ref", ""),
                 json.dumps(r["attrs"], sort_keys=True, default=str)))
        self._db.commit()
        return {"stored": len(rows) - refused, "refused": refused}

    def events(self, kind: str | None = None, subject: str | None = None,
               since: str | None = None, until: str | None = None,
               limit: int = 10000) -> list[dict[str, Any]]:
        q = ("SELECT kind,ts,subject,outcome,source,source_ref,attrs"
             " FROM events WHERE 1=1")
        args: list[Any] = []
        if kind:
            q += " AND kind=?"; args.append(kind)
        if subject:
            q += " AND subject=?"; args.append(subject)
        if since:
            q += " AND ts>=?"; args.append(since)
        if until:
            q += " AND ts<=?"; args.append(until)
        q += " ORDER BY ts LIMIT ?"; args.append(limit)
        rows = self._db.execute(q, args).fetchall()
        return [{"kind": k, "ts": t, "subject": s, "outcome": o,
                 "source": src, "source_ref": ref,
                 "attrs": json.loads(a)}
                for k, t, s, o, src, ref, a in rows]

    def hydrate_engine(self, engine, window: str | None = None,
                       since: str | None = None) -> int:
        """Feed a HistoryEngine from stored events (§316)."""
        n = 0
        for e in self.events(since=since):
            n += engine.ingest_events(e["kind"], [{
                "ts": e["ts"], "subject": e["subject"],
                "outcome": e["outcome"], **e["attrs"]}], e["source"])
        return n

    # -- snapshots / patterns ---------------------------------------

    def put_snapshot(self, fleet_id: str, doc: dict[str, Any],
                     taken_at: str | None = None) -> None:
        self._db.execute(
            "INSERT INTO snapshots(fleet_id, taken_at, doc)"
            " VALUES(?,?,?)",
            (fleet_id, taken_at or _utcnow(),
             json.dumps(doc, sort_keys=True, default=str)))
        self._db.commit()

    def snapshots(self, fleet_id: str | None = None,
                  limit: int = 100) -> list[dict[str, Any]]:
        q = "SELECT fleet_id,taken_at,doc FROM snapshots"
        args: list[Any] = []
        if fleet_id:
            q += " WHERE fleet_id=?"; args.append(fleet_id)
        q += " ORDER BY taken_at DESC LIMIT ?"; args.append(limit)
        return [{"fleet_id": f, "taken_at": t, "doc": json.loads(d)}
                for f, t, d in self._db.execute(q, args).fetchall()]

    def put_pattern(self, pattern_id: str, window: str,
                    doc: dict[str, Any]) -> None:
        self._db.execute(
            "INSERT INTO patterns(pattern_id, window, computed_at, doc)"
            " VALUES(?,?,?,?)",
            (pattern_id, window, _utcnow(),
             json.dumps(doc, sort_keys=True, default=str)))
        self._db.commit()

    # -- retention + deletion (§319–321) ------------------------------

    def gc(self, event_days: int = 90,
           snapshot_days: int = 365) -> dict[str, int]:
        """Retention GC — deterministic counts of deleted rows."""
        now = datetime.now(timezone.utc)
        cut_e = (now - timedelta(days=event_days)).isoformat()
        cut_s = (now - timedelta(days=snapshot_days)).isoformat()
        de = self._db.execute(
            "DELETE FROM events WHERE ts<?", (cut_e,)).rowcount
        ds = self._db.execute(
            "DELETE FROM snapshots WHERE taken_at<?", (cut_s,)).rowcount
        self._db.commit()
        return {"events_deleted": de, "snapshots_deleted": ds}

    def forget_subject(self, subject: str) -> dict[str, Any]:
        """§321 — right-to-forget: delete every event for a subject.
        Returns an audit receipt; never a silent no-op."""
        n = self._db.execute(
            "DELETE FROM events WHERE subject=?",
            (subject,)).rowcount
        self._db.commit()
        return {"forgotten": subject, "events_deleted": n,
                "receipt": "right-to-forget executed" if n
                else "no rows matched — nothing to forget"}

    def vacuum(self) -> dict[str, Any]:
        """§215 — compaction. Returns measured bytes before/after so the
        claim is auditable, not asserted."""
        before = (Path(self.path).stat().st_size
                  if self.path != ":memory:" else None)
        self._db.execute("VACUUM")
        self._db.execute("ANALYZE")
        self._db.commit()
        after = (Path(self.path).stat().st_size
                 if self.path != ":memory:" else None)
        return {"vacuumed": True, "bytes_before": before,
                "bytes_after": after}

    def stats(self) -> dict[str, Any]:
        """Self-metrics (§322): row counts + storage footprint."""
        counts = {t: self._db.execute(
            f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ("events", "snapshots", "patterns")}
        size = Path(self.path).stat().st_size \
            if self.path != ":memory:" and Path(self.path).exists() \
            else None
        return {"rows": counts, "storage_bytes": size,
                "telemetry": "local-only"}
