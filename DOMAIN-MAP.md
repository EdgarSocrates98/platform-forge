# DOMAIN MAP — Platform Forge

## Ownership lines (what Platform Forge answers)

`where software runs · how it gets there · how it is governed · how it is
observed · how reliable it is · how secure it is · how much it costs · who owns
it · what a change can affect`

| Domain | Package | Canonical questions | Primary artifacts |
|---|---|---|---|
| core/evidence | `core`, `models` | what do we know, at what tier? | facts, findings, receipts, refusals |
| kernel/economy | `tokensave`, `rtk`, `caveman`, `economy`, `routing` | minimum context, honest accounting | context packs, ledger, qpt |
| sdd | `sdd` | is the change governed end-to-end? | phase artifacts, gates, hash cascade |
| graph | `graph` | what depends on what, with what provenance? | nodes, edges, snapshots, diffs |
| iac | `iac` | declared infra: safe? drifting? versioned? | HCL/plan/state |
| kubernetes | `kubernetes`, `k8s` | workloads: reliable, secure, sized? | manifests, Helm, Kustomize, Gateway, Cilium/Hubble, autoscaling |
| gitops | `gitops` | desired↔observed sync, health, promotion | ArgoCD/Flux (AppSet/AppProject/waves) |
| cicd | `cicd` | pipeline: least-privilege, signed, traceable? | workflow files |
| observability | `observe`, `observability` | telemetry coverage & correlation | OTel, Prometheus, Grafana |
| sre | `sre`, `observe` | SLOs, budgets, incidents, capacity, DR | SLO contracts, metrics, postmortem |
| finops | `finops` | cost allocation, units, anomalies | CUR/Azure/GCP/OpenCost/Kubecost, FOCUS |
| security | `security`, `policy` | IAM paths, secrets, supply chain, policy | policies, SBOM, SLSA, Cosign, Kyverno |
| platform_product | `product` | maturity, golden paths, catalog, adoption | catalog entities, scorecards |
| cloud | `cloud/{common,aws,azure,gcp}` | provider→common model mapping | cloud dumps (T1 provider-observed) |
| ownership | `core/ownership` | who owns it — and who disagrees? | CODEOWNERS, Backstage, tags, labels |
| change/risk | `sandbox`, `risk`, `plan` | what does this change touch, in what order? | reviews, risk decompositions, remediation DAGs |
| capability/interop | `mcp/registry`, `forge` | what can this forge do, and for whom? | contracts, manifests, A2A envelopes |
| live | `live` | what is actually running, how fresh is the evidence? | observation envelopes, collectors, reconcile, topology, drift journal |
| lab/evals | `lab`, `evals` | does the machinery prove itself? | scenarios, eval corpus, coverage, precision |
| ops/control-plane | `ops` | governed change: intent→plan→approve→execute→verify→audit | `ops/*`, typed actions, envelopes, ledger, store, rollback materials/plans (ROLLBACK.md) |
| store/bench | `core/artifacts`, `bench` | what does it cost to know? | artifact store, measured benchmarks |

## Explicit non-goals

- Deep API design (api-forge), data-workload internals (spark-forge-aws),
  general security operations (future Security Forge).
- Golden paths never trap teams: `happy path + supported variants + escape hatch`.
- The core never mutates: `approve`/`apply` refuse; execution is host-side.

## Cross-domain rules

- Edges keep provenance: `observed | planned | declared | inferred` +
  `confidence` + `source_fact_ids`. A generated plan produces `planned`,
  never `observed`; cross-repo name joins are `inferred`.
- Correlation ≠ causation: incident engine emits `confirmed | supported |
  candidate | contradicted | unknown`, never blame-by-ordering.
- Contradictions surface both states as `state.contradiction` — never
  averaged into one silent winner.
- Every analyzer is version-aware via the source registry; an unknown
  version yields `unresolved`, not a verdict.
