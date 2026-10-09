# ADR-0056 — BudgetEnvelope dimensions and hard/soft limits

Status: accepted · economy cycle (FE-002)

## Context

Budgets were per-subsystem ints; nothing distinguished a target from a wall, and spend could cross silently.

## Decision

Eleven dimensions (context_bytes … money) each carry soft+hard limits; phase and role budgets narrow the envelope; protected items (critical evidence, unresolved markers, security findings, rollback info) and protected phases (VERIFY/SECURITY/CONTRACT) can never be removed for cost. Hard overrun is a named verdict, never silent.

## Consequences

Economy pressure is structurally incapable of cutting safety or evidence.
