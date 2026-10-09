# ADR-0042 — Agents vs engines

Status: accepted · cycle 5.1

## Context

It is cheap to let an agent "just do" analysis; that erodes the
deterministic core and makes results unreproducible.

## Decision

Agents are operators of deterministic engines, never replacements.
Executors (pf-*) wrap `collect`, `judge`, `diff`, `graph` — they cannot
delegate and run on the deterministic model tier. Specialists compose
engine output into findings; engines produce the evidence.

## Consequences

Every claim traces to a deterministic computation + fact_id. The agent
layer can change without invalidating evidence.
