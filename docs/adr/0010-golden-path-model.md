# ADR-0010 — Golden paths are evidence-checked, not just templates

Status: accepted · cycle 2

## Context

A golden path that is only a template proves nothing about whether teams
follow it or whether it still reflects reality.

## Decision

- `product/golden_paths/` models a golden path as: scaffold + guardrails
  (rules) + signals the platform can measure (evidence hooks).
- Analysis reports `coverage` (which signals were observed) separately
  from `conformance` (which rules passed) — an unscaffolded repo is
  `unresolved`, never a zero.
- `escape hatch` is first-class: deviations are labeled, not blocked.

## Consequences

Golden-path status is evidence-bound; adoption claims require measured
signals, and gaps surface as named unknowns.
