# ADR-0003 — Token economy by architecture, not by prompt

Status: accepted · 2026-10-06

## Context

"Send the repo to the model" fails on cost and correctness. Both sibling forges
built native economy subsystems (TokenSave/RTK/Caveman equivalents, ledgers,
routing tables) instead of depending on external tools.

## Decision

- First-party `tokensave` (input/context economy: content addressing, FTS5
  index, context packs, delta reading, budgets, ledger), `rtk` (command-output
  compaction with lazy expand), `caveman` (output compression with protected
  spans + receipts).
- Economy claims require benchmarks: `evals/` compares baseline vs tokensave
  context on identical cases; quality gates gate the saving claim.
- Adaptive routing is data (`rules/catalog/routing.yaml`), not model judgment.

## Consequences

Economy is a measurable property of the system, and any regression is caught by
evals rather than discovered in a bill.
