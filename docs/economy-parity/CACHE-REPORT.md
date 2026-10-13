# Cache Report

`platformforge/economy/cache.py` — evidence for the multilayer cache
contract.

## Invalidation semantics proven by tests

- Rule-catalog change → `fact` layer hits, `finding`/`analysis` layers
  miss (selective invalidation — eval E2 + `test_economy_cache.py`).
- Knowledge-hash change → `analysis`/`context` miss, `fact` hits.
- TTL expiry → `stale`, never served as fresh (eval: stale observation).
- `invalidate_dep` removes only entries bound to the changed dep —
  transitive and selective.
- Sensitive payloads refused at `put` — secrets never persist.
- Every `get` emits a `CacheDecision` receipt with state, layer,
  changed_deps and entry age.

## Stats surface

`cache stats` → hits, misses, bytes_reused, entries, invalidations,
per-layer counts. `cache gc` removes expired entries; `cache inspect`
returns decision+payload for a key.

## Fleet integration

Fleet aggregates cache under keys embedding the snapshot hash — a new
snapshot is a different key (a miss), never a stale hit
(`collection.fleet_query_cache_*`, tested in `test_economy_fleet_qpt.py`).

## Overhead

Measured: put ~222µs, hit ~2.6ms, miss ~3.8ms (file-backed JSON;
ECONOMY-BENCHMARKS.md). Hits avoid layer recomputation — the saving is
the recompute, not the lookup.
