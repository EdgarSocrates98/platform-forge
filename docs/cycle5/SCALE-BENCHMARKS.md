# Cycle 5 — Benchmarks (measured, not claimed)

Method: `platformforge bench scale` — `perf_counter` ms on seeded
synthetic service graphs (deterministic shape per n), `tracemalloc`
KiB for build peak, SQLite store with bulk inserts. Numbers are local
to this machine and this run — a baseline, not a scale claim.

## Graph + store, 2025 benchmark run

| n svc | nodes | edges | build ms | merge ms | dependents ms | blast ms | diff ms | ser ms | deser ms | peak KiB | store ins ms | store q ms | forget ms | store B |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 50 | 58 | 200 | 1.53 | 1.72 | 0.07 | 0.12 | 10.45 | 0.24 | 0.27 | 120.3 | 3.82 | 0.38 | 0.05 | 40960 |
| 200 | 208 | 800 | 4.05 | 5.9 | 0.19 | 0.28 | 161.58 | 0.68 | 0.87 | 473.4 | 6.46 | 0.98 | 0.05 | 65536 |
| 800 | 808 | 3200 | 14.23 | 24.19 | 0.58 | 0.49 | 1438.79 | 3.17 | 10.66 | 1888.6 | 12.85 | 3.91 | 0.12 | 155648 |

## Honest readings

- Graph build/merge/dependents/blast scale sub-linearly→linearly in
  this shape (fanout 3, 8 clusters); all well under interactive
  latency at n=800.
- `diff` is the dominant cost — O(nodes×edges) matching, ~1.4s at
  3.2k edges. Acceptable for snapshot diff; a known target if
  profiling shows it matters in practice.
- Store bulk insert (`put_events`, single commit) ≈0.06ms/event;
  per-event `put_event` commits each row (~3.5ms/event) — bulk is
  the documented ingestion path.
- No extrapolated claims: numbers cover the measured sizes only.
