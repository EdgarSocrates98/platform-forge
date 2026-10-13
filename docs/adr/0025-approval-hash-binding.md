# ADR-0025 — Approval binds to the exact object hash (TOCTOU)

Status: accepted · cycle 4

## Context

Approving "the plan" is meaningless if the plan can change between
approval and execution — the classic time-of-check/time-of-use gap.

## Decision

- `Approval.subject_hash` = canonical hash of the approved object
  (ChangePlan/ExecutionEnvelope). Any content change → new hash →
  approval invalid.
- Execution-time revalidation: plan hash, approval TTL + scope +
  parameter bounds, observation freshness, policy still-allows.
- Approvals are scope-bound (resource A ≠ resource B) and
  parameter-bound (replicas 3→5 ≠ 3→50).

## Consequences

- Stale approval and plan mutation are named refusal paths, not edge
  cases.
