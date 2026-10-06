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
  provenance: observed | declared | inferred
  confidence: 0.0..1.0
  source_fact_ids: [PF-K8S-00123]
```

An inferred edge is never rendered as observed. Facts feed edges 1:1.

## Algorithms

blast radius, upstream/downstream deps, transitive deps, critical paths,
single points of failure, cycles, orphans, ownership gaps, unmonitored
workloads, unprotected resources, unallocated costs, unreachable resources,
external exposure, identity chains, network paths, deployment paths, GitOps
paths, supply-chain paths.

## Graph diff

`graph_before` vs `graph_after` → `nodes_added/removed, edges_added/removed,
exposure_changed, identity_changed, ownership_changed, cost_changed,
HA_changed, SLO_changed, security_changed` → feeds the change-risk engine.

## Canonical questions it must answer

- "If I change this Terraform module, what can be affected?"
- "Who depends on this cluster?" / "Which app uses this secret?"
- "Which pipeline produced this image?" / "Which SLO covers this service?"
- "Who owns this resource?" / "Which cost center absorbs this workload?"

## Discipline

Graph proximity is not proven causality. Blast radius reports
`direct | transitive | runtime | security | reliability | cost | compliance |
unknown` impact classes separately.
