# ADR-0053 — Unified economy control plane

Status: accepted · economy cycle (FE-002)

## Context

Token, tool, provider and agent spend lived in separate ledgers with
no shared contract; each subsystem optimized locally and none could
answer "what did this run cost" end-to-end.

## Decision

One Economy Control Plane: `EconomyPlan` (contract + explainability),
`BudgetEnvelope` (limits), the multilayer `CacheStore`, the
`ContextGateway`, the routing control plane, `EconomyCheckpoint`, and
`BudgetReconciliation` — all feeding `EconomyLedger` + `unified_view`.
Agents operate the deterministic engines; they never replace them.

## Consequences

Every run can answer cost/reuse/routing questions with receipts.
Unobserved data is `unresolved`, never zero. The plane itself must not
cost more than it saves — measured in `docs/economy-parity/BENCHMARKS.md`.
