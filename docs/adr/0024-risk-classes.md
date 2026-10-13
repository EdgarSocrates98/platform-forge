# ADR-0024 — Mutation risk classes R0–R5 and unknown≠low

Status: accepted · cycle 4

## Context

"Risk" as a single score hides the dimension that matters (data loss
vs latency). Operations need a risk *class* plus decomposed dimensions.

## Decision

- Classes: R0 read-only · R1 non-impacting metadata · R2 reversible
  low-risk · R3 operational · R4 production-impacting · R5 destructive/
  identity/security/data-critical.
- Dimensions scored separately: blast radius, environment, criticality,
  reversibility, security/identity/network/data/availability/cost
  impact, uncertainty, freshness, coverage, rollback confidence.
- `Reversibility ∈ {fully,conditionally,hard,irreversible,unknown}` —
  never invented; unknown reversibility raises the class.

## Consequences

- `unknown` maps to the safe side everywhere: unknown risk is not low
  risk; unknown rollback is not reversible.
