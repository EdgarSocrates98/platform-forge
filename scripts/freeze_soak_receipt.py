#!/usr/bin/env python3
"""§105–§110 — SOAK-RECEIPT generator.

Runs the analytics soak at scale, the determinism double-run (same
workload twice → identical canonical result hash), and the v1→v2
migration replay. Writes docs/freeze/SOAK-RECEIPT.json bound to HEAD.

Usage: python scripts/freeze_soak_receipt.py [--write] [--events N]
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RECEIPT = REPO / "docs" / "freeze" / "SOAK-RECEIPT.json"


def _canon_hash(d: dict) -> str:
    """Hash only semantic fields — timings vary, outcomes must not."""
    keep = {k: v for k, v in d.items()
            if k not in ("bulk_insert_ms", "query_total_ms", "gc_ms",
                         "forget_ms", "vacuum_ms", "peak_insert_kib")}
    return hashlib.sha256(json.dumps(keep, sort_keys=True,
                                     default=str).encode()).hexdigest()


def main() -> int:
    write = "--write" in sys.argv
    events = 100_000
    for a in sys.argv:
        if a.startswith("--events="):
            events = int(a.split("=", 1)[1])
    sys.path.insert(0, str(REPO))
    from platformforge.analytics.soak import run_migration_replay, run_soak

    soak = run_soak(events=events, rounds=10)
    soak2 = run_soak(events=events, rounds=10)
    determinism = {
        "hash_a": _canon_hash(soak), "hash_b": _canon_hash(soak2),
        "identical": _canon_hash(soak) == _canon_hash(soak2),
        "note": "canonical hash over semantic fields (rows/gc/verdict/"
                "reopen/crash) — timings excluded by design"}
    migration = run_migration_replay()
    sha = subprocess.run(["git", "rev-parse", "HEAD"], check=False,
                         capture_output=True, text=True).stdout.strip()
    receipt = {"schema": "platformforge/soak-receipt/v1", "sha": sha,
               "soak": soak, "determinism": determinism,
               "migration": migration,
               "verdict": "pass" if (soak["verdict"] == "pass"
                                     and determinism["identical"]
                                     and migration.get("migrated"))
               else "fail"}
    if write:
        RECEIPT.write_text(json.dumps(receipt, indent=2,
                                      sort_keys=True) + "\n")
        print(f"written {RECEIPT} verdict={receipt['verdict']}")
    else:
        print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["verdict"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
