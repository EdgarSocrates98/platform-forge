# DOMAIN MAP — Platform Forge

## Ownership lines (what Platform Forge answers)

`where software runs · how it gets there · how it is governed · how it is
observed · how reliable it is · how secure it is · how much it costs · who owns
it · what a change can affect`

| Domain | Package | Canonical questions | Primary artifacts |
|---|---|---|---|
| core/evidence | `core`, `models` | what do we know, at what tier? | facts, findings, receipts |
| kernel/economy | `tokensave`, `rtk`, `caveman`, `economy`, `routing` | minimum context, honest accounting | context packs, ledger |
| sdd | `sdd` | is the change governed end-to-end? | phase artifacts, gates |
| graph | `graph` | what depends on what, with what provenance? | nodes, edges, diffs |
| iac | `iac` | declared infra: safe? drifting? versioned? | HCL/plan/state |
| kubernetes | `kubernetes` | workloads: reliable, secure, sized? | manifests, events, exports |
| gitops | `gitops` | desired↔observed sync, health, promotion | ArgoCD/Flux manifests |
| cicd | `cicd` | pipeline: least-privilege, signed, traceable? | workflow files |
| observability | `observability` | telemetry coverage & correlation | OTel, Prometheus config |
| sre | `sre` | SLOs, budgets, incidents, capacity, DR | SLO contracts, metrics dumps |
| finops | `finops` | cost allocation, units, anomalies | billing exports, OpenCost |
| security | `security`, `policy` | IAM, secrets, supply chain, policy | policies, SBOM, attestations |
| platform_product | `platform_product` | maturity, golden paths, catalog, adoption | catalog entities, surveys |
| cloud | `cloud/{common,aws,azure,gcp}` | provider mapping to common concepts | cloud dumps/config |

## Explicit non-goals

- Deep API design (api-forge), data-workload internals (spark-forge-aws),
  general security operations (future Security Forge).
- Golden paths never trap teams: `happy path + supported variants + escape hatch`.

## Cross-domain rules

- Edges keep provenance: `observed | declared | inferred` + `confidence` +
  `source_fact_ids`. An inferred edge is never reported as observed.
- Correlation ≠ causation: incident engine emits `confirmed | supported |
  candidate | contradicted | unknown`, never blame-by-ordering.
- Every analyzer is version-aware via the source registry.
