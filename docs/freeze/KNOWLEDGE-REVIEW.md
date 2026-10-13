# KNOWLEDGE-REVIEW — freeze sweep (§113–§116)

Generated from `platformforge knowledge` + rule-catalog source_refs on 2026-10-08.
States: current | aging | stale | unverified (registry computes the first three; unverified = no retrieved_at).

| source | product | status | retrieved_at | rules citing |
|---|---|---|---|---|
| kubernetes-docs | Kubernetes | current | 2026-10-06 | 22 |
| argocd-docs | Argo CD | current | 2026-10-06 | 6 |
| google-sre-book | Google SRE Book / Workbook | current | 2026-10-06 | 5 |
| aws-iam-docs | AWS Identity and Access Management | current | 2026-10-06 | 4 |
| github-actions-docs | GitHub Actions | current | 2026-10-06 | 4 |
| backstage-docs | Backstage | current | 2026-10-06 | 2 |
| kyverno-docs | Kyverno | current | 2026-10-06 | 2 |
| argo-rollouts-docs | Argo Rollouts | current | 2026-10-06 | 1 |
| aws-docs | Amazon Web Services | current | 2026-10-06 | 1 |
| aws-s3-docs | Amazon S3 | current | 2026-10-06 | 1 |
| aws-vpc-docs | Amazon Virtual Private Cloud | current | 2026-10-06 | 1 |
| crossplane-docs | Crossplane | current | 2026-10-06 | 1 |
| finops-framework | FinOps Framework | current | 2026-10-06 | 1 |
| flux-docs | Flux | current | 2026-10-06 | 1 |
| focus-spec | FOCUS (FinOps Open Cost and Usage Specification) | current | 2026-10-06 | 1 |
| gateway-api | Kubernetes Gateway API | current | 2026-10-06 | 1 |
| github-security-docs | GitHub code security | current | 2026-10-06 | 1 |
| github-securitylab | GitHub Security Lab | current | 2026-10-06 | 1 |
| nvd | NIST National Vulnerability Database | current | 2026-10-06 | 1 |
| osv | OSV.dev vulnerability database | current | 2026-10-06 | 1 |
| api-forge | api-forge (sibling Forge) | current | 2026-10-06 | 0 |
| aws-eks-docs | Amazon Elastic Kubernetes Service | current | 2026-10-06 | 0 |
| aws-organizations-docs | AWS Organizations | current | 2026-10-06 | 0 |
| azure-docs | Microsoft Azure | current | 2026-10-06 | 0 |
| cert-manager-docs | cert-manager | current | 2026-10-06 | 0 |
| checkov-docs | Checkov | current | 2026-10-06 | 0 |
| cilium-docs | Cilium / Hubble | current | 2026-10-06 | 0 |
| cncf-landscape | CNCF Landscape | current | 2026-10-06 | 0 |
| cncf-maturity-model | CNCF Platform Engineering Maturity Model | current | 2026-10-06 | 0 |
| cyclonedx-spec | CycloneDX | current | 2026-10-06 | 0 |
| dora-platforms | DORA platform engineering capabilities | current | 2026-10-06 | 0 |
| eso-docs | External Secrets Operator | current | 2026-10-06 | 0 |
| gcp-docs | Google Cloud | current | 2026-10-06 | 0 |
| gitlab-ci-docs | GitLab CI | current | 2026-10-06 | 0 |
| grafana-docs | Grafana | current | 2026-10-06 | 0 |
| helm-docs | Helm | current | 2026-10-06 | 0 |
| in-toto-spec | in-toto | current | 2026-10-06 | 0 |
| istio-docs | Istio | current | 2026-10-06 | 0 |
| jenkins-docs | Jenkins | current | 2026-10-06 | 0 |
| karpenter-docs | Karpenter | current | 2026-10-06 | 0 |
| keda-docs | KEDA | current | 2026-10-06 | 0 |
| kubecost-docs | Kubecost | current | 2026-10-06 | 0 |
| kustomize-docs | Kustomize | current | 2026-10-06 | 0 |
| linkerd-docs | Linkerd | current | 2026-10-06 | 0 |
| opa-docs | OPA / Gatekeeper | current | 2026-10-06 | 0 |
| opencost-docs | OpenCost | current | 2026-10-06 | 0 |
| opentelemetry-docs | OpenTelemetry | current | 2026-10-06 | 0 |
| opentofu-docs | OpenTofu | current | 2026-10-06 | 0 |
| prometheus-docs | Prometheus | current | 2026-10-06 | 0 |
| pulumi-docs | Pulumi | current | 2026-10-06 | 0 |
| ? |  | ? |  | 0 |

## High-impact sources

Sources ranked by rule-citation count — staleness here hurts most:

- **kubernetes-docs** (current) — 22 rules
- **argocd-docs** (current) — 6 rules
- **google-sre-book** (current) — 5 rules
- **aws-iam-docs** (current) — 4 rules
- **github-actions-docs** (current) — 4 rules
- **backstage-docs** (current) — 2 rules
- **kyverno-docs** (current) — 2 rules
- **argo-rollouts-docs** (current) — 1 rules
- **aws-docs** (current) — 1 rules
- **aws-s3-docs** (current) — 1 rules

## Cadence (§228–§230 — process, not automated promise)

- **monthly**: `platformforge knowledge` — review `stale`/`conflicted`/`unresolved`, bump `retrieved_at` only after checking the source
- **quarterly**: compatibility sweep — Python 3.10–3.13, k8s tracked releases, Terraform/OpenTofu, Crossplane v1/v2, ArgoCD, AWS API assumptions
- **release-triggered**: every source cited by a changed rule gets re-verified before ship
- **security**: dependency + SBOM review on every release candidate
