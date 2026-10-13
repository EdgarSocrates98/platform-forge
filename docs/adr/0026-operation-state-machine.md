# ADR-0026 — Explicit operation state machine + append-only ledger

Status: accepted · cycle 4

## Context

Without an explicit state machine, "did it run? did it work?" becomes
log archaeology. Operations must be inspectable, resumable, auditable.

## Decision

- `Operation` states: draft → planned → simulated → policy-reviewed →
  awaiting-approval → approved → scheduled → executing → verifying →
  {converged, partially-converged, failed} → rollback states → terminal.
  Invalid transitions refuse (`draft→executing` impossible).
- `OperationLedger` append-only per operation: every transition emits a
  receipt with actor (human/agent/host/system — never mixed).
- `OperationLock` per canonical resource; conflicting operations
  block/queue/arbitrate. Idempotency keys dedup retries; resume
  re-validates environment+approval, never blindly re-executes.

## Consequences

- Partial failure is explicit state, not corruption; compensation is a
  modeled path, not improvisation.
