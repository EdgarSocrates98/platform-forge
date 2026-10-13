# ADR-0004 — Planned edges are never promoted to observed

Status: accepted · cycle 2

## Context

The graph used to treat `GENERATED_PLAN` (T2 — a Terraform plan, an ArgoCD
app's declared target) as `observed` provenance. A plan is intent, not
reality: the apply may never have run.

## Decision

- `PROVENANCES = {observed, planned, declared, inferred}`; T2 facts produce
  `planned` edges, T3 `declared`, T0/T1 `observed`, cross-member name joins
  `inferred` (confidence < 1).
- Node `state` is resolved from the strongest contributing fact
  (observed > planned > desired > inferred) and stored in `node.attrs`.
- Graph diff, blast radius and plans report provenance; `planned` is shown
  as `planned`, never silently upgraded.

## Consequences

`graph diff` can distinguish "the plan says X" from "AWS reports X".
Cross-repo joins carry `inferred` provenance so they can be challenged.
