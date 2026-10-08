"""Phase N — analytics soak: bulk, retention, forget, vacuum, restart,
crash rollback, migration replay (§213–217)."""

from __future__ import annotations

from platformforge.analytics.soak import run_migration_replay, run_soak


def test_soak_small_run_all_phases_pass():
    r = run_soak(events=2000, rounds=4)
    assert r["verdict"] == "pass"
    assert r["rows_before_gc"] > r["rows_after_gc"]      # retention ran
    assert r["reopen_rows_intact"]                      # restart safe
    assert r["crash_rollback_ok"]                       # crash safe
    assert r["vacuum"]["vacuumed"]
    assert r["schema_version"] >= 2


def test_soak_retention_and_forget_counts_exact():
    r = run_soak(events=1000, rounds=2)
    # gc deletes exactly what's left after forget — exact accounting
    assert r["gc"]["events_deleted"] == \
        r["rows_before_gc"] - r["forgotten"] - r["rows_after_gc"]
    assert r["forgotten"] > 0


def test_migration_replay_v1_to_current():
    r = run_migration_replay()
    assert r["migrated"]
    assert r["from_version"] == 1
    assert r["index_present"]
    assert r["rows_preserved"] == 1
