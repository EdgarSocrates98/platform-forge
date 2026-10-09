# ADR-0041 — Canonical agent roster

Status: accepted · cycle 5.1

## Context

Agents existed as names scattered across routing tables and host
configs; Cycle 5 routed six names that didn't exist.

## Decision

One canonical `AgentSpec` v2 roster in `platformforge/agents/roster.py`
(41 agents). All mirrors, routing, and delegation resolve against it;
`agents-contract`/`agents-routing` gates fail on dangling names.

## Consequences

No agent exists only on one host. Renames go through `LEGACY_NAMES`.
Routing drift is a build failure, not a runtime surprise.
