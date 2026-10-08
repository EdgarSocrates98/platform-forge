# ADR-0045 — Agent budget model

Status: accepted · cycle 5.1

## Context

Agent runs need hard ceilings, and exhaustion must be honest.

## Decision

`AgentRunEnvelope` charges model calls, context bytes, tool calls,
agents, fanout, duration before spend. Classes: tiny/small/standard/
deep/critical. Exhaustion → `partial` refusal, never silent success.
Safety, evidence, and unresolved reporting are budget-exempt.

## Consequences

Budget overflow produces a receipted partial result. A run can never
spend its way out of declaring `unresolved`.
