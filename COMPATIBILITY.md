# Compatibility matrix

Platform Forge core is deterministic and offline-first; versions below
concern the **host adapters** and the artifacts/standards we parse or
drive. "Supported" means covered by fixtures/evals; absence means
*unresolved*, not unsupported-by-assertion.

## Runtime

| Component | Supported | Notes |
|---|---|---|
| Python | 3.10, 3.11, 3.12, 3.13 | `requires-python = ">=3.10"` |
| PyYAML | >=6 | fixtures, evals, config |
| MCP | >=2.2,<3 | optional extra `mcp` |
| boto3 | >=1.34,<2 | optional extra `cloud` (host adapters only) |

## Execution adapters (cycle 4)

| Adapter | Interface | Verified against | Notes |
|---|---|---|---|
| git | git CLI >= 2.30 | unit tests (stub transport) | branch/patch/commit/PR-body only |
| terraform | terraform CLI >= 1.5 | unit tests | `validate`/`plan`/`show -json`/saved-plan `apply` |
| tofu | OpenTofu CLI >= 1.6 | unit tests | same contract as terraform |
| argocd | argocd CLI >= 2.9 | unit tests | `app diff`/`sync`/`rollback`; never bypasses GitOps |
| kubernetes | kubectl >= 1.28 | unit tests + lab | scale / rollout-restart / annotate(JSON-patch+resourceVersion) / rollout-status |

## Observation collectors (cycle 3)

| Collector | Interface | Verified | Coverage |
|---|---|---|---|
| kubernetes | kubectl get -o json | lab fixtures + evals | workloads, services, ns, nodes, endpointslice, secrets(metadata) |
| aws | aws CLI >= 2.13 | lab fixtures + evals | ec2, iam, s3, eks, rds, lambda, elb (core set) |

## Schemas

| Schema | Version | Stability |
|---|---|---|
| observation-envelope | v1 (cycle3) | stable |
| graph | v2 (cycle3) | stable, v1 reads auto-upgrade on write |
| change-intent / change-plan | v1 | stable |
| execution-envelope | v1 | stable |
| policy-decision | v1 | stable |
| operation-store | v2 | forward-migrating |
| capability-manifest | v3 | supersedes v2 (adds operations + cross_forge) |

## Deprecation

See `DEPRECATION.md`. Breaking changes ride schema_version bumps with
in-repo migrations; nothing removes silently.
