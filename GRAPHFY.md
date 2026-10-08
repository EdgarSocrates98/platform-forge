# GRAPHFY — the platform graph engine (`platformforge/graph`)

Graphfy is the core asset: platform engineering *is* dependencies. The graph is
built only from facts — never from guesses — and every edge carries provenance.

## Node kinds (initial vocabulary, `platformforge/graph/vocab.py`)

`repository, component, service, api, pipeline, workflow, artifact,
container_image, sbom, team, owner, cloud_account, subscription, project,
organization, region, zone, vpc_vnet, subnet, route, gateway, nat,
load_balancer, dns, certificate, cluster, node_pool, node, namespace, workload,
pod, k8s_service, ingress, iam_principal, role, policy, service_account,
workload_identity, secret, database, cache, queue, topic, bucket, volume,
terraform_module, terraform_resource, crossplane_xr, argocd_application,
fluxcd_resource, monitor, dashboard, alert, slo, cost_center, budget,
billing_unit, security_policy, admission_policy`

Node `state` is resolved from the strongest contributing fact:
`observed > planned > desired > inferred` — stored on `node.attrs` so a
planned-only cluster is never rendered as existing.

## Edge kinds

`owns, depends_on, deploys_to, runs_on, contained_by, routes_to, calls,
publishes_to, consumes, reads, writes, assumes, impersonates, can_access,
uses_secret, exposes, secured_by, observed_by, alerted_by, governed_by,
provisioned_by, generated_by, billed_to, replicated_to, fails_over_to`

## Edge provenance (mandatory)

```yaml
edge:
  kind: uses_secret
  from: workload/payments
  to:   secret/db-creds
  provenance: observed | planned | declared | inferred
  confidence: 0.0..1.0
  source_fact_ids: [PF-K8S-00123]
```

`planned` comes from T2 generated-plan facts (a Terraform plan, an ArgoCD
desired state) — intent, never promoted to `observed` (ADR-0004).
`inferred` covers cross-member joins and heuristics (`confidence < 1`,
`via` recorded). Facts feed edges; `source_fact_ids` prove them.

## Derived edges

- **Delivery graph** — repo → pipeline → image → GitOps app → workload
  chains joined across fact collections.
- **Cross-repo** — `workspace.yaml` members: application→gitops→cluster,
  infra→cluster, namespace matches — all `inferred`, challengeable.
- **Identity paths** — principal→role chaining (`graph identity-*`).

## Algorithms

blast radius (per impact class), upstream/downstream deps, transitive
deps, critical paths, single points of failure, cycles, orphans,
ownership gaps, unmonitored workloads, unprotected resources,
unallocated costs, unreachable resources, external exposure, identity
chains, network paths, deployment paths, GitOps paths, supply-chain
paths.

## Snapshots & diff

`graph snapshots` persists a versioned envelope (source types, counts,
hash). `graph diff` / `diff --before --after` → semantic categories:
`nodes_added/removed, edges_added/removed, exposure_changed,
identity_changed, ownership_changed, cost_changed, HA_changed,
SLO_changed, security_changed` — each entry cites `fact_ids` and feeds
the change-risk engine.

## Canonical questions it must answer

- "If I change this Terraform module, what can be affected?"
- "Who depends on this cluster?" / "Which app uses this secret?"
- "Which pipeline produced this image?" / "Which SLO covers this service?"
- "Who owns this resource?" / "Which cost center absorbs this workload?"
- "Can this principal become that role?" (`identity-become` — a
  no-path-found is a named result, never "no risk")

## Discipline

Graph proximity is not proven causality. Blast radius reports
`direct | transitive | runtime | security | reliability | cost |
compliance | unknown` impact classes separately.

## Temporal & multi-layer edges (v2, Cycle 3)

- `Edge.temporal = {first_seen, last_seen, sample_count, expired?}` —
  observed edges carry when the platform showed them.
- `Edge.evidence = [Evidence(source_ref, tier, provenance)]` — one edge
  accumulates layers from every contributing provenance; `layers()`
  returns them. Merging same-id edges unions evidence, never drops.
- `graph/temporal.py` — `edges_between(t0,t1)` window queries;
  `expire_stale_edges(now, max_age_s)` marks `temporal.expired=true`.
  **Marked, never deleted** — history stays auditable.
- v1→v2 migration: `migrate.py` upgrades persisted snapshots
  (synthesizes evidence layers from v1 provenance); v1 loads stay
  byte-identical (upgrade is on-write, not on-read — graph_hash stable).
- Runtime edges land on the `observed` layer via
  `graph.apply_runtime_edges` — runtime evidence never overwrites
  declared provenance.
