# ADR-0028 — Verification ≠ command success

Status: accepted · cycle 4

## Context

`terraform apply` exit 0 does not mean "service healthy". Treating
command success as outcome success is the most common ops lie.

## Decision

- Verification compares `ExpectedDelta` vs `ObservedDelta` from live
  observation (provider state, k8s status, runtime topology, SLO,
  metrics) across windows: immediate / stabilization / extended.
- Convergence states: converged · partially-converged · not-converged ·
  regressed · unknown.
- SLO degradation after a change → verification failure → rollback
  path, even when the executor reported success.

## Consequences

- "Applied" never upgrades to "converged" without observed evidence.
