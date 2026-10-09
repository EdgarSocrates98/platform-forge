# ADR-0051 — Fleet-scale context policy

Status: accepted · cycle 5.1

## Context

"Analyze the fleet" naively = send fleet to the model.

## Decision

Fleet tasks route to the fleet coordinator with bounded member fanout
(`max_parallelism: 6`) and per-member context packs; results aggregate
deterministically. Whole-fleet context is refused, not truncated.

## Consequences

Fleet analysis scales with graph scope + per-member packs, not with
one giant prompt.
