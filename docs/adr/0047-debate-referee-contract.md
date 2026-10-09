# ADR-0047 — Debate/referee contract

Status: accepted · cycle 5.1

## Context

Multi-agent disagreement needs a bound, not a loop.

## Decision

`Debate`: 2 specialists + critic + referee, 1–3 rounds, evidence-cited
positions only (no-evidence positions refused at intake). Referee emits
`winner|tied|unresolved` over 10 axes + receipt. Verifier still runs.

## Consequences

Disagreement terminates with a receipt or an honest `unresolved`.
`tied` is a legitimate outcome.
