# ADR-0023 — Autonomy is per-capability, max A4 in Cycle 4

Status: accepted · cycle 4

## Context

A global autonomy switch would let a weak capability inherit the
privileges of a strong one. Autonomy must be earned per capability.

## Decision

- Levels A0 observe / A1 recommend / A2 plan / A3 prepare / A4 execute
  with human approval / A5 auto-execute low-risk / A6 closed-loop.
- Each capability declares `max_autonomy`; there is no global level.
- Cycle 4 target: **A4 functional**. A5 is permitted only for narrow,
  proven, reversible, non-production, lab-validated uses (e.g. PR
  generation, dev restart). **A6 is a non-goal.**

## Consequences

- `live capability`/`ops` surfaces report autonomy per capability;
  requests above the cap refuse, not silently downgrade.
