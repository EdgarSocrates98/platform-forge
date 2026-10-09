# ADR-0057 — Checkpoint and resume carry spend

Status: accepted · economy cycle (FE-002)

## Context

A resumed run restarted its accounting at zero, so tokens/tools/provider calls vanished across restarts.

## Decision

EconomyCheckpoint persists run_id, spent+remaining budget, context/cache refs, agent state, routing+risk profile, tool+provider spend and dep hashes. Resume revalidates artifact/knowledge/policy deps (stale deps flag re-verification) and cannot downgrade the profile (PF-CHECKPOINT-DOWNGRADE).

## Consequences

Interrupted work resumes honest — spend accumulates across restarts and stale world-state is surfaced, not trusted.
