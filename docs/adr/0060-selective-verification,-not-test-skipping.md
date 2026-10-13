# ADR-0060 — Selective verification, not test skipping

Status: accepted · economy cycle (FE-002)

## Context

Verification ran everything or nothing; neither is honest under budget.

## Decision

VerificationPlanner picks the smallest sufficient tier set (V0..V5) from risk, change scope, graph impact and security touch; risk sets a floor that budget pressure cannot lower (security-verification is always selected when security is touched). Skipped tiers are recorded with reasons.

## Consequences

Verification is impact-scoped and auditable; economy cannot weaken a floor.
