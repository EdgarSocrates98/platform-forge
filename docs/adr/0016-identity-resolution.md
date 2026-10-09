# ADR-0016 — Identity resolution is explainable and confidence-tiered

Status: accepted · cycle 3

## Context

The same resource appears as Terraform address, ARN, K8s object, AWS
Config item, CloudTrail resource, OTel resource. Correlating them by
name alone causes cross-cluster collisions and false merges.

## Decision

- `ResourceIdentity`: canonical_id + aliases + provider_ids +
  graph_nodes + evidence — a registry, not a heuristic pile.
- Strong identifiers merge with confidence 1.0: ARN exact match, K8s
  UID, provider-native immutable id. Scoped identity (cluster_id +
  namespace + kind + name) is strong-but-not-immutable. Name-only
  matches are low-confidence and never auto-merge.
- Every link carries {confidence, provenance, fact_ids, reason};
  conflicts (e.g., SA annotation → Role A vs Pod Identity → Role B) are
  explicit `identity-drift`/conflict findings, never silently resolved.

## Consequences

- Multi-cluster: `cluster_uid + object uid` is the global identity —
  `prod/api` in two clusters stays two nodes.
- EKS ↔ Kubernetes cluster linking requires provider evidence
  (ARN/API-server identity), never kubeconfig context names.
