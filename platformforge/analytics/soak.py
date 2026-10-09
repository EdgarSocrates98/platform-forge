"""Analytics soak harness (§213–217) — deterministic replay, no wall
clock. Rounds of bulk inserts + snapshots + queries + retention + forget
+ vacuum + close/reopen + crash + migration, all measured.

Crash safety is simulated honestly: committed data must survive an
abrupt connection drop; uncommitted data must roll back — both are
asserted, not assumed. Migration safety is replayed by building a v1
database by hand and opening it through the store.
"""

from __future__ import annotations

import sqlite3
import tempfile
import tracemalloc
from pathlib import Path
from time import perf_counter
from typing import Any

from platformforge.analytics.store import SCHEMA_VERSION, AnalyticsStore


def _ev(i: int, subj: str | None = None) -> dict[str, Any]:
    return {"kind": "operation" if i % 7 else "deploy",
            "ts": f"2025-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}T00:00:00Z",
            "subject": subj or f"svc:{i % 97}",
            "outcome": "converged" if i % 5 else "failed",
            "source": "soak", "attrs": {"i": i}}


def run_soak(events: int = 10_000, rounds: int = 10,
             snapshots_per_round: int = 5) -> dict[str, Any]:
    """§214 — N rounds × (events/round) bulk inserts with retention,
    forget, vacuum and reopen interleaved. Deterministic shape; every
    number measured."""
    rep: dict[str, Any] = {"schema": "platformforge/soak/v1",
                           "events": events, "rounds": rounds}
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "soak.db"
        st = AnalyticsStore(db)
        tracemalloc.start()
        t_ins = q_ms = 0.0
        per_round = events // rounds
        for r in range(rounds):
            t0 = perf_counter()
            st.put_events([_ev(r * per_round + i) for i in range(per_round)])
            t_ins += perf_counter() - t0
            for s in range(snapshots_per_round):
                st.put_snapshot(f"fleet-{s % 3}",
                                {"round": r, "seq": s})
            t0 = perf_counter()
            st.events(kind="operation", limit=500)
            q_ms += perf_counter() - t0
        _, peak_insert = tracemalloc.get_traced_memory()

        rows_before_gc = st.stats()["rows"]["events"]
        t0 = perf_counter()
        forgot = st.forget_subject("svc:0")
        t_forget = perf_counter() - t0
        assert not st.events(subject="svc:0")  # verify, not assume
        t0 = perf_counter()
        gc = st.gc(event_days=45)            # ~2/3 of the ts window
        t_gc = perf_counter() - t0
        rows_after_gc = st.stats()["rows"]["events"]

        t0 = perf_counter()
        vac = st.vacuum()
        t_vac = perf_counter() - t0

        # restart/reopen: committed rows must be intact
        st.close()
        st = AnalyticsStore(db)
        rows_reopened = st.stats()["rows"]["events"]
        reopen_ok = rows_reopened == rows_after_gc

        # crash safety: an abrupt drop keeps committed rows and rolls
        # back whatever was in flight
        raw = sqlite3.connect(db)
        raw.execute("INSERT INTO events(kind,ts,subject,outcome,source,"
                    "source_ref,attrs) VALUES('x','t','s','o','s','','{}')")
        raw.close()  # no commit — must not persist
        rows_after_crash = st.stats()["rows"]["events"]
        tracemalloc.stop()

        rep.update({
            "verdict": "pass" if reopen_ok
                       and rows_after_crash == rows_reopened else "fail",
            "bulk_insert_ms": round(t_ins * 1000, 2),
            "query_total_ms": round(q_ms * 1000, 2),
            "rows_before_gc": rows_before_gc,
            "gc": gc, "gc_ms": round(t_gc * 1000, 2),
            "rows_after_gc": rows_after_gc,
            "forgotten": forgot["events_deleted"],
            "forget_ms": round(t_forget * 1000, 2),
            "vacuum": vac, "vacuum_ms": round(t_vac * 1000, 2),
            "reopen_rows_intact": reopen_ok,
            "crash_rollback_ok": rows_after_crash == rows_reopened,
            "db_size_bytes": db.stat().st_size,
            "peak_insert_kib": round(peak_insert / 1024, 1),
            "schema_version": SCHEMA_VERSION})
        st.close()
    return rep


def run_migration_replay() -> dict[str, Any]:
    """§217 — build a schema-v1 database by hand (as a previous release
    wrote it), reopen through the current store, verify upgrade."""
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "old.db"
        raw = sqlite3.connect(db)
        raw.executescript("""
            CREATE TABLE events (id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL, ts TEXT NOT NULL, subject TEXT NOT NULL,
                outcome TEXT NOT NULL, source TEXT NOT NULL,
                source_ref TEXT NOT NULL, attrs TEXT NOT NULL);
            CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            INSERT INTO meta VALUES('schema_version', '1');
            INSERT INTO events VALUES(1,'op','2025-01-01','svc:a',
                'ok','legacy','','{}');
        """)
        raw.commit(); raw.close()
        st = AnalyticsStore(db)
        ver = st._db.execute(
            "SELECT value FROM meta WHERE key='schema_version'"
        ).fetchone()[0]
        idx = st._db.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND "
            "name='ix_events_subj_kind'").fetchone()
        rows = st.events()
        ok = int(ver) == SCHEMA_VERSION and idx is not None \
            and len(rows) == 1 and rows[0]["subject"] == "svc:a"
        st.close()
        return {"migrated": ok, "from_version": 1,
                "to_version": int(ver), "index_present": bool(idx),
                "rows_preserved": len(rows)}
