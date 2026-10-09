# Cycle 5.1 — Scale Benchmarks

`platformforge bench scale` — measured on this host (`perf_counter`
ms, `tracemalloc` KiB, seeded synthetic graphs). Reproduce:

```bash
uv run platformforge bench scale --sizes 50,200,800,2000,10000
```

## Graph diff optimization (Phase M)

Pre-optimization, `diff()` ran `blast_radius` per shared node —
O(N·(V+E)); ~3.9 s at 800 nodes, ~51 s at 5 000 nodes.

Post-optimization: incremental blast-delta candidates restricted to
changed dependency edges, SCC condensation, memoized integer-bitset
ancestor cones with Kahn ordering. Verified equivalent to brute force
on 80 randomized trials (incl. node removal).

**~154× faster at 5 000 nodes.**

## Measured (this host)

| Nodes | Edges | Build | Diff | Blast | Serialize |
|---|---|---|---|---|---|
| 50 | ~200 | 0.9 ms | 1.7 ms | — | — |
| 200 | ~800 | 4.7 ms | 6.4 ms | — | — |
| 800 | ~3 200 | 15 ms | 29 ms | — | — |
| 2 000 | ~8 000 | 32 ms | 98 ms | — | — |
| 10 000 | 40 000 | 192 ms | 637 ms | 8 ms (192 blast nodes) | 38 ms |

10 000-node graph: 23 MiB build peak, store insert 105 ms,
store query 28 ms, store size 1.6 MiB.

## Edge-density sweep (10 000 nodes)

| Target edges | Build | Diff |
|---|---|---|
| 100 000 | — | 1.5 s |
| 250 000 | — | 3.2 s |
| 500 000 | — | 5.7 s |

## Unsupported targets

Sizes estimated over the host memory budget return
`unsupported-on-host` with a reason — never a hang, never an
extrapolated claim. 100 000-node and denser runs were not attempted
on this host and are not extrapolated from the numbers above.
