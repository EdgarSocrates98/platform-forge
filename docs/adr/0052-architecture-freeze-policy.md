# ADR-0052 — Architecture freeze policy

Status: accepted · cycle 5.1

## Context

Cycle 5.1 completes the agentic runtime; continued layering without a
freeze invites drift.

## Decision

After Phase P, no new architectural capability lands without an
explicit unfreeze decision recorded in `FREEZE-REVIEW.md`. Bug fixes,
evidence backfill, and documentation are not frozen — new verbs,
agents, and orchestration modes are.

## Consequences

Stability becomes a declared posture; the freeze review is a gate
artifact, not a vibe.
