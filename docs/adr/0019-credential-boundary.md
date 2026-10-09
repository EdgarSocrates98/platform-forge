# ADR-0019 — Credentials live in the host; the platform never sees them

Status: accepted · cycle 3

## Context

Live collection needs credentials. The Forge interop delegates tasks but
must never receive credentials. Collectors must not mint or read secret
material.

## Decision

- Host-native chains only: AWS CLI profile/env/role-assumption/SDK
  default chain; kubeconfig current/explicit context or in-cluster
  config. No platform secret store.
- Credentials are never serialized/stored/logged/in receipts/facts/
  MCP/A2A payloads. Preflight records account + principal ARN only.
- Forbidden API surface is allowlist-based: K8s `pods/exec|attach`,
  `port-forward`, `serviceaccounts/token`, Secret values; AWS
  `GetSecretValue`, `KMS:Decrypt`, `ssm:GetParameter(WithDecryption)`,
  and all mutating prefixes. `Get*` prefix alone is insufficient —
  value-read actions are excluded by name (AWS's own ReadOnlyAccess
  includes GetSecretValue — proof prefixes are not enough).
- `doctor --deep` probes adapter availability without collecting.

## Consequences

- Minimal-permission docs/generators (read-only RBAC, scoped IAM policy)
  are part of the product surface.
- Secret-property tests cover envelope/store/graph/MCP/receipt/A2A.
