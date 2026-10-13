# ADR-0036 — Optimization → ChangeIntent boundary

Status: accepted · cycle 5

## Context

Recommendations that execute skip governance; recommendations that only describe do nothing.

## Decision

OptimizationEngine.plan() is the only bridge — it emits a governed ChangeIntent (reason=recommendation, risk_context with rec confidence); the Cycle 4 pipeline re-evaluates everything.

## Consequences

Optimization cannot bypass policy/approval/verify; uncertain opportunities are suppressed, visible in portfolio.suppressed.
