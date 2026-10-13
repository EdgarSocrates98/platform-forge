# AGENTIC-OS — agents, routing, arbitration

Agents are a composition layer over real engines — never a substitute for
deterministic work, never marketing-shaped ("not 100 agents for the count").

## Classes

| Class | Role |
|---|---|
| coordinators | own a domain question, decide which specialists/engines run next |
| specialists | deep single-domain analysis calling the real engines |
| reviewers | judge output per axis (architecture, security, reliability, cost, evidence, platform-product, change-risk) |
| critics | adversarial check on evidence quality and false positives |
| referees | arbitrate disagreements — never average |
| executors | deterministic workers (extract, judge, verify, synthesize) |

## Coordinators (initial roster)

`platform-coordinator` (umbrella), `cloud-coordinator`, `kubernetes-coordinator`,
`iac-coordinator`, `gitops-coordinator`, `sre-coordinator`,
`observability-coordinator`, `finops-coordinator`, `security-coordinator`,
`incident-coordinator`.

## Specialists (initial set — each has a distinct operational reason)

platform-architect, backstage-specialist, crossplane-specialist,
aws/azure/gcp-platform-specialist, terraform-specialist, opentofu-specialist,
kubernetes-{core,networking,security,storage,scheduling,autoscaling},
helm-specialist, kustomize-specialist, argocd-specialist, flux-specialist,
cilium-specialist, service-mesh-specialist, github-actions-specialist,
gitlab-ci-specialist, jenkins-specialist, opentelemetry-specialist,
prometheus-specialist, sre-specialist, slo-specialist, capacity-specialist,
incident-specialist, dr-specialist, finops-specialist, iam-specialist,
policy-specialist, supply-chain-specialist, developer-platform-specialist.

## Adaptive routing (`platformforge/routing`)

Route is **computed**, not chosen by vibes: task type, complexity, risk,
evidence availability, domain, blast radius, security sensitivity, cost impact.

```text
simple manifest lint        → deterministic engine only
moderate k8s issue          → k8s specialist
cross-account architecture  → coordinator + specialists + reviewer
production incident         → incident coordinator + relevant specialists
security-sensitive change   → mandatory security reviewer
```

Routing table: `rules/catalog/routing.yaml` (data, not code).

## Referee arbitration (v2)

When specialists disagree, `agents referee` scores each position on six
axes — **tier, freshness, version compatibility, scope, contradictions,
completeness** — and returns `{winner, scores, unresolved, refusal,
receipt_id}`. A position with absent evidence cannot win as a confident
conclusion; the outcome can be `unresolved` with a named refusal.
Never average positions; contradictory evidence is preserved, not
smoothed over.

## Cost of reasoning

Every model call is ledgered (model, calls, input/output/cache tokens, latency,
monetary cost if known, task, result, quality). `platformforge economy report`
exposes the ledger. Budgets never cover safety, evidence or `unresolved`
reporting.
