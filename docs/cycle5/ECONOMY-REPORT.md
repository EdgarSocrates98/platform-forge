# Cycle 5 — Economy Report

Fleet-scale context economics: the TokenSave/economy surface at
org scope, plus what it costs *this repo* to run its own gates.

## Fleet pack strategy (Phase L)

`economy/fleetpack.py` — when a task targets a fleet question, the
pack prefers: fleet question answer → member snapshots →
evidence-tiered facts. Budgets never cover safety/evidence/unresolved
reporting (same rule as the rest of the platform).

Measured: pack over the acme fixture assembles bounded member
contexts without full-fleet dumps (full dumps are refused by the
delegation contract — `PF-OPS-CROSSFORGE-REFUSED`).

## Store/storage economics (measured)

From `platformforge bench scale` (see SCALE-BENCHMARKS.md):

- AnalyticsStore bulk `put_events`: ~0.06 ms/event amortized
  (single commit); per-event `put_event` ≈3.3–11 ms (commit per
  row) — bulk is the documented ingestion path.
- SQLite store at 800-service scale: ~155 KB on disk.
- Graph build peak memory (tracemalloc): 120 KiB @ n=50 →
  1.9 MiB @ n=800 — sub-linear vs naive adjacency copies.

## What a validation run costs

The full `scripts/validate.py` run executes 30+ gates including
pytest (~700 tests), lab (43 scenarios) and evals (82 cases).
`fleet-*` gates add seconds, not minutes — the suite is dominated
by the pre-existing test corpus.

## Self-cost honesty

No token spend is claimed by analytics outputs themselves —
economics are measured on the `economy`/`tokens` surfaces and
reported as measured values, never estimates.
