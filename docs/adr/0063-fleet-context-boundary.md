# ADR-0063 — Fleet context boundary

Status: accepted · economy cycle (FE-002)

## Context

Fleet questions could pull the entire org inventory into context.

## Decision

Fleet context is a funnel: org → fleet summary → affected clusters/services → graph neighborhood → evidence. Full fleet payloads never enter a capsule (refs only); fleet aggregates cache under keys that embed the snapshot hash so a new snapshot is a miss, never stale; fleet_delta diffs member refs so repeat questions recompute only the change.

## Consequences

Fleet-scale questions stay bounded and fresh by construction.
