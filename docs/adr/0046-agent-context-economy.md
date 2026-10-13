# ADR-0046 — Agent context economy

Status: accepted · cycle 5.1

## Context

The default agent failure is "send the repo as context".

## Decision

`Task → Graph scope → Evidence → ContextPack`. Packs carry task
summary, cited evidence, bounded graph neighborhood, rules, knowledge
refs, recent ops, open questions. Follow-ups get `previous_hash +
delta`. Fleet scope is bounded — whole-fleet dumps refused.

## Consequences

Context size is a budgeted, hashed artifact. Reuse shows up as
`cache_reuse` in the run ledger.
