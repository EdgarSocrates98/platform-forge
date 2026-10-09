# ADR-0008 — Economy is measured per task, never asserted globally

Status: accepted · cycle 2

## Context

"Tokensave saves tokens" is unfalsifiable without measuring quality lost
per byte saved, on real tasks.

## Decision

- `economy qpt` compares `full` vs `tokensave` context on the same task
  and reports measured `quality_per_token` (evidence completeness,
  fact/rule survival) — never a global percentage claim.
- `evals token_economy` cases assert floors (critical evidence survives
  compression) rather than a target ratio.
- `bench tokens` measures caveman compression on small/medium/large
  eval fixtures; results are baselines labeled `measured, not a claim`.
- The ledger records `payload_bytes` and never invents provider tokens.

## Consequences

A compression ratio is reported as a measurement on this corpus, this
run — alongside what evidence survived — not as a marketing figure.
