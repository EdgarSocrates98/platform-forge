# ADR-0030 — Policy precedence is explicit; deny wins on tie

Status: accepted · cycle 4

## Context

Multiple policy sources (native, OPA, Kyverno, CEL) can conflict.
Choosing one arbitrarily is unaccountable.

## Decision

- Policies carry `{owner, authority, priority, scope}`. Evaluation
  orders by declared priority; on equal priority, **deny dominates
  allow** and `require-*` dominates plain allow.
- A conflict between equal-priority allow/deny produces `unresolved`
  (surfaced to the referee) — never a coin flip.
- `PolicyException` must carry `expires_at` and returns to enforced on
  expiry; `shadow` policies produce `would_*` verdicts that never
  enforce.

## Consequences

- The canonical contract is `PolicyDecision` with a receipt —
  OPA/Kyverno are input engines, not truth.
