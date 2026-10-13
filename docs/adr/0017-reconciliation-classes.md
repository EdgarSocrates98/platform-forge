# ADR-0017 — Reconciliation classifies drift; it never returns a boolean

Status: accepted · cycle 3

## Context

desired↔observed boolean drift is too poor for live platforms: planned
changes, out-of-band edits, controller-generated children, defaults and
computed fields all masquerade as drift.

## Decision

- Reconciler input: desired + planned + observed (+optional runtime)
  snapshots with their timestamps.
- Output is a classified result over the §102 class set (converged,
  planned-not-applied, observed-out-of-band, desired-missing-observed,
  observed-orphan, config-drift, identity-drift, policy-drift,
  security-drift, network-drift, version-drift, runtime-undeclared,
  stale-observation, permission-unknown, scope-mismatch, uncomparable,
  unknown).
- Normalization before comparison: TF computed fields, K8s
  server-populated fields (resourceVersion/managedFields/uid/status) and
  API defaults are stripped; controller-owned resources (ownerRefs) are
  not orphans.
- `converging` and `stabilization_window` model eventual consistency.
- Every reconciliation emits a receipt (input snapshots, freshness,
  coverage, normalizers applied, matches, unresolved comparisons).

## Consequences

- False-positive drift is a tested-against bug class, not noise.
- Temporal skew between inputs degrades confidence explicitly.
