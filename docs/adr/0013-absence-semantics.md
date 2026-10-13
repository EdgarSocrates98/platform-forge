# ADR-0013 — Absence is a claim that requires proof

Status: accepted · cycle 3

## Context

"Not returned by the API" is routinely misread as "does not exist."
Partial coverage, permission gaps, staleness and sampling all produce
false absence.

## Decision

- `resource does not exist` verdicts require: scope covers the target
  ∧ coverage=complete for that resource type ∧ snapshot fresh.
- Otherwise absence resolves to `unresolved` — never to a positive
  "deleted"/"missing" claim.
- Deletion requires strong evidence (K8s DELETED event, AWS Config
  ResourceDeleted, explicit provider delete state) → `deleted`
  tombstone; missing-from-partial → `unknown`, never `deleted`.

## Consequences

- Property test: partial observation + missing resource MUST NOT yield
  confirmed absence (cycle §196).
- Findings that depend on non-existence inherit `unresolved` and surface
  the coverage reason.
