# ADR-0061 — Agent fanout economy

Status: accepted · economy cycle (FE-002)

## Context

Fan-out was unbounded — agents multiplied on ambiguity and each cost context+tools.

## Decision

AgentUniqueness audits unique/duplicated/refuted/discarded contribution per run; zero-contribution agents are flagged as unused_agent candidates for routing review (recommendation, never auto-fix). Fanout limits live in the envelope (agents, parallelism, debate rounds); debates group rounds deterministically and stop when a round adds no new evidence.

## Consequences

Agent spend is accountable per run; waste is visible and the router may only be changed by review.
