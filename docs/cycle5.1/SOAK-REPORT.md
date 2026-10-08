# Cycle 5.1 — Soak Report

`platformforge/analytics/soak.py` — deterministic replay against the
analytics SQLite store: bulk insert, query, right-to-forget, retention
GC, vacuum, restart, crash rollback, schema migration.

## Measured (5 000 events × 3 rounds)

| Operation | Time |
|---|---|
| bulk insert | 175 ms |
| queries (all windows) | 22 ms total |
| forget_subject (svc:0) | 4.6 ms — 52 rows deleted |
| retention GC (45d) | 15.6 ms — 4 946 rows deleted |
| vacuum | 7.7 ms — 872 KiB → 48 KiB |
| peak insert memory | ~1 MiB |

## Invariants proven

- **Restart**: reopening the store preserves all committed rows
  (`reopen_rows_intact: true`).
- **Crash**: an abrupt connection drop rolls back in-flight writes,
  keeps committed rows (`crash_rollback_ok: true`).
- **Forget before GC**: subject deletion is verified empty before
  retention GC runs — exact accounting, no rows escape via ordering.
- **Migration replay**: v1 → v2 schema applies the declared migration
  chain, records it in `meta`, preserves rows (`migrated: true`).
- **Counts exact**: `gc.events_deleted == rows_before_gc − forgotten
  − rows_after_gc` — every deleted row is accounted for.

## Schema versioning

`SCHEMA_VERSION = 2`; `_MIGRATIONS` is a declared, recorded chain —
v2 adds `ix_events_subj_kind`. No silent DDL.

## Banned payload keys (enforced at insert)

`secret`, `password`, `token`, `api_key`, `private_key`,
`credential`, `authorization` — payloads containing them are refused.

## Limits

Single-node SQLite only. No claim is made about concurrent writers,
network replicas, or multi-GB stores — those are host-side concerns.
