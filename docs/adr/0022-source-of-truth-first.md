# ADR-0022 — Source-of-truth-first remediation

Status: accepted · cycle 4

## Context

Direct provider mutation (`kubectl patch`, AWS API calls) fights the
controller that owns the resource: GitOps reconciles it back, Terraform
drifts, and the "fix" evaporates — worse, it is invisible to review.

## Decision

- `SourceOfTruthResolver` runs before any remediation plan: ArgoCD app
  → Git repo; Terraform state → Terraform repo; Crossplane MR →
  XR/Composition; Helm release → chart source; unmanaged → provider
  API only as explicit last resort.
- When ownership cannot be proven: `PF-OPS-SOURCE-UNKNOWN` → human
  review. Never guess.
- GitOps-first and Terraform-first are policy defaults, not
  conventions.

## Consequences

- The common remediation is a PR against the source of truth — which
  is reviewable, revertible and auditable by construction.
