# ADR-0050 — Agent operation boundary

Status: accepted · cycle 5.1

## Context

Agents must never reach production mutation through the offline core.

## Decision

No agent spec lists mutation verbs; coordinators' write scope is run
state only. `change approve|apply` stays a host-side governed action
refused in core (`PF-OPS-*`). Mirrors can't add permissions.

## Consequences

Production mutation requires the Cycle-4 governance path — a human
gate an agent cannot mint.
