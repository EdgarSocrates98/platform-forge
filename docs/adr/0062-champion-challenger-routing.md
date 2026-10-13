# ADR-0062 — Champion/challenger routing

Status: accepted · economy cycle (FE-002)

## Context

The router could not evolve without silently changing behavior.

## Decision

The live route is champion; candidates run in shadow. Promotion requires quality floor pass + unchanged safety + better economy AND human approval — there is no auto-promotion path. Every decision emits a receipt binding inputs, policy_version, decision, reason and estimated budget.

## Consequences

Routing can improve measurably while the plane stays human-governed.
