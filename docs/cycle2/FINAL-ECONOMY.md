# CYCLE 2 — FINAL ECONOMY REPORT (§187)

All figures are **measured on this repo's eval fixtures in this run**
(`platformforge bench`), labeled `measured, not a claim` — ADR-0008.
Nothing here is a marketing ratio.

## `bench run` — local baseline (34 fixtures, 50 facts, 3 runs)

| Operation | median s | min s |
|---|---|---|
| index_time (31 files) | 0.1497 | 0.1486 |
| analyze_all | ~0.000 | ~0.000 |
| graph_build | 0.0005 | 0.0005 |
| rule_execution | 0.0024 | 0.0024 |
| context_build | 0.0266 | 0.0259 |

## `bench tokens` — Caveman compression, measured bytes

| Tier | files | raw_bytes | compact_bytes | ratio | median s |
|---|---|---|---|---|---|
| small | 11 | 945 | 922 | 0.976 | 0.0007 |
| medium | 11 | 3038 | 2742 | 0.903 | 0.0017 |
| large | 12 | 21346 | 20601 | 0.965 | 0.0101 |

Ratios here are modest — the fixtures are already dense JSON. The point
is the *method*, not the number: a ratio is reported alongside what
evidence survived, never as a standalone "X% saved".

## `economy qpt` — quality per token

`economy qpt --task <t> --input-budget <n>` runs the same task `full` vs
`tokensave` and reports `quality_per_token` = evidence preserved /
tokens spent. `token_economy` evals assert a floor (critical evidence —
`fact_id`, `rule_id`, risks, `unresolved` markers — survives), not a
compression target.

## Ledger v2

Every tool call records `payload_bytes` (measured). `provider_tokens` is
`tokens_unresolved` unless a host transcript supplies it — never
inferred from bytes.

## What is NOT claimed

- No global "N% token savings" figure.
- No cost-in-USD estimate without a measured billing input.
- No throughput extrapolation to production-sized graphs from these
  fixture timings.
