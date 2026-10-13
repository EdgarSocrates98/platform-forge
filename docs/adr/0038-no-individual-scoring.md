# ADR-0038 — No individual developer scoring

Status: accepted · cycle 5

## Context

Platform friction metrics tempt surveillance; person-level data is out of scope by design.

## Decision

dx_metrics measures team/platform friction; FORBIDDEN_METRICS keys are dropped from input; guard_no_person_metrics audits output; privacy config pins are non-overridable.

## Consequences

No per-person metric can be emitted even with hostile input; config cannot weaken the pin.
