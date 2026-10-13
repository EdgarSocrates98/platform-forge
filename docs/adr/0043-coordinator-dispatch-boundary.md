# ADR-0043 — Coordinator dispatch boundary

Status: accepted · cycle 5.1

## Context

Unbounded fanout is the cheapest way to blow a token budget.

## Decision

Coordinators (incident/change/fleet/optimization/product) dispatch via
closed `delegates_to` lists with `max_parallelism` caps (3–6), collect
structured findings, and hold `state-writer` access to run state only.

## Consequences

Fanout is a declared, audited number. Coordinators cannot reach
infrastructure — only run state under `.platformforge/`.
