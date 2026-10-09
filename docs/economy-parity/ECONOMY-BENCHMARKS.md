# Economy Control Plane — Benchmarks

Two sections (polish §39): **Control Plane Overhead** — measured cost of
the economy layer itself — and **End-to-End Economy Evidence** — what
the plane saves on real workloads. They are different claims and are
never conflated (§38: microbench ≠ savings bench).

Source: `scripts/bench_economy.py`; raw data:
`docs/economy-parity/BENCHMARKS.json`. Synthetic payloads, local
filesystem, python 3.12.3 — reproduce before quoting.

## Control Plane Overhead

## Overhead per operation (median / p95, microseconds)

| Operation | n | median µs | p95 µs | Interpretation |
|---|---:|---:|---:|---|
| cache put | 100 | 222 | 282 | content-hash + JSON write |
| cache get (hit) | 100 | 2,601 | 2,817 | file read + dep compare |
| cache get (miss) | 100 | 3,829 | 4,314 | miss path is the expensive one (dep diff) |
| cache stats | 20 | 1,226 | 1,285 | dir scan over 200 entries |
| context build (50 facts) | 50 | 850 | 903 | dedup + capsule + persist + ledger |
| context inspect | 50 | 45 | 61 | read stored capsule |
| context expand | 50 | 45 | 50 | section slice |
| router route | 200 | 8,327 | 8,420 | route table + mode logic |
| routing profile floor | 500 | 0.6 | 0.7 | pure lookup |
| ledger record | 100 | 23 | 30 | append-only JSONL |
| budget check | 500 | 2.7 | 2.9 | envelope compare |

## What the numbers say — and do not say

- The control plane's per-decision overhead is **sub-millisecond to
  single-digit-milliseconds** — noise next to any model call or
  provider round-trip it governs.
- Cache hits (~2.6 ms) are dominated by file-backed JSON reads; a
  hit still avoids recomputation of the layer it serves, which is
  where the real economy lives. No speedup claim is made beyond that.
- `router route` (~8 ms) is the heaviest single decision — it scans
  the route table and domain rules. Bounded and deterministic; worth
  watching if it is ever on a hot path.
- `context_bytes_by_mode` shows identical bytes across modes for the
  synthetic payload — modes differ by *budget ceiling*, not by a
  claimed reduction. A savings claim requires a real workload
  comparison (QPT corpus), not this microbench.

## Modes benchmarked

`full`, `tokensave`, `cache`, `deep` capsules measured; per-mode cost
axes are recorded by `quality_per_cost` (tokens, bytes, tool_calls,
model_calls, agents, provider_calls, wall_time, money) with unmeasured
axes reported `unresolved`.

## End-to-End Economy Evidence

**insufficient evidence** (§40). No production workload corpus exists
yet, so no end-to-end savings number is claimed — not "X% cheaper",
not projected savings. What exists is verified machinery:
`quality_per_cost` computes per-dimension reductions only when quality
floors pass, and reports `unresolved` for unmeasured axes (money is
unresolved without declared pricing + observed usage). When a real
corpus lands, this section gets a measured table — until then the
honest answer is that the control plane's *cost* is measured and its
*savings* are evidence-dependent.
