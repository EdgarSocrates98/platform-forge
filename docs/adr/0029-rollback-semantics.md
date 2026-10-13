# ADR-0029 — Rollback is preplanned, risk-aware, verified

Status: accepted · cycle 4

## Context

Rollback invented during an incident is not rollback — it is a second
unplanned change under stress.

## Decision

- Every R3+ operation carries a `RollbackPlan` (trigger, strategy,
  actions, preconditions, limitations, data impact, expected delta)
  evaluated *before* execution.
- Types: git revert · terraform revert · previous artifact · argo
  rollback · rollout undo · compensating operation · manual-only ·
  impossible. Unknown rollback raises risk; `impossible` blocks
  autonomy.
- Rollback outcomes are verified like forward changes — a rollback
  that makes things worse is reported, not hidden.
- Automatic rollback: Lab/non-prod only this cycle.

## Consequences

- Compensation (saga-like) is modeled per step for non-transactional
  flows.
