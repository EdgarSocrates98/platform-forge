# MULTI-CLUSTER — registry & federation

`live/federation.py` + `platformforge live clusters`.

## Cluster registry

`ClusterRegistry` (`.platformforge/clusters.json`) stores declared
clusters: `name`, `provider` (eks|gke|aks|kind|external), `context`/
`kubeconfig` (k8s), `account`/`region` (cloud), `workload_identity`,
`api_endpoint`, `labels`. `live clusters --register <json>` adds;
`live clusters` lists with availability hints.

Identity is federated: a k8s `uid` is scoped per cluster; AWS
ARNs are scoped per account+region. `identity.py` resolves within a
scope and flags same-name-different-cluster objects as distinct —
collisions are `identity.conflict`, not merges.

## Federation view

Multiple observation envelopes (one per cluster scope) reconcile into
a single report: per-scope verdicts plus cross-scope entries
(`federated: true`) when the same workload exists in two clusters and
drifted asymmetrically — e.g. a deploy rolled to one cluster only.

The graph keeps a `cluster` attribute on observed nodes and
`replicated_to`/`fails_over_to` edges for multi-cluster relations
(node kinds `cluster`, `crossplane_*`, `argocd_application`,
`fluxcd_resource` already in vocab).

## Honest limits

- Federation requires an observation per cluster in scope — partial
  federation coverage is reported in `coverage`, not smoothed over.
- No cross-cluster causality: a failing cluster + a healthy replica
  does not become "failover happened" without `fails_over_to` + event
  evidence.
- Registry auth fields are references (context names, role ARNs), never
  credentials — the file can live in the repo; transports resolve creds
  on the host at collection time.
