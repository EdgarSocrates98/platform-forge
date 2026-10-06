# CAPABILITIES — Platform Forge capability matrix

Machine-readable source of truth: `platformforge/mcp/registry.py`
(`CAPABILITIES`). CLI verbs and MCP tools are projections of this registry —
`platformforge capability list|describe|manifest` and the MCP adapter read
the same data. Parity is tested, not assumed (`tests/test_mcp.py`).

Each capability declares:

```yaml
id: platform.k8s.analyze
version: "1"
inputs: [k8s-manifests]
outputs: [facts, findings]
risk: read-only            # read-only | propose | mutating
required_evidence: [t3-repo-config]
offline: true
mutable: false
cost_class: deterministic  # deterministic | indexed | local-model | provider-model
agent_requirements: []     # specialists this capability can dispatch to
```

## Matrix (initial)

| Capability ID | Phase | Domain | Offline | Notes |
|---|---|---|---|---|
| `platform.inspect` | 1 | core | yes | inventory artifacts of a repo/workspace |
| `platform.init` | 1 | core | yes | scaffold `.platformforge/` |
| `platform.status` | 1 | core | yes | workspace + cache + freshness status |
| `platform.doctor` | 1 | core | yes | environment health-check |
| `platform.collect` | 5+ | * | optional | ingress adapters (file/git/k8s-export/cloud dumps) |
| `platform.analyze` | 5+ | * | yes | extract facts from artifacts |
| `platform.correlate` | 4 | core | yes | join facts across domains |
| `platform.graph.build` | 4 | graph | yes | facts→nodes/edges with provenance |
| `platform.graph.query` | 4 | graph | yes | blast radius, deps, paths, gaps |
| `platform.graph.diff` | 4 | graph | yes | before/after node+edge+exposure delta |
| `platform.judge` | 1 | core | yes | apply rule catalog to facts |
| `platform.diagnose` | 8 | sre | yes | correlate symptoms→candidates (never cause-as-certainty) |
| `platform.explain` | 2 | core | yes | render evidence chain for a finding |
| `platform.recommend` | 11 | * | yes | findings+context→recommendations w/ evidence |
| `platform.plan` | 5+ | * | yes | change plan (sandboxed) |
| `platform.diff` | 5+ | * | yes | desired↔observed diff |
| `platform.drift` | 5+ | * | yes | drift detection (tfstate, gitops) |
| `platform.impact` | 4 | graph | yes | change impact via graph diff + blast radius |
| `platform.sdd.*` | 3 | sdd | yes | lifecycle verbs + gates |
| `platform.economy.report` | 2 | economy | yes | measured bytes/tokens, ledger |
| `platform.tokens.*` | 2 | tokensave | yes | index, packs, budget, ledger |
| `platform.context.*` | 2 | tokensave | yes | context packs, delta reading |
| `platform.policy.check` | 10 | security | yes | policy-as-code evaluation |
| `platform.security.*` | 10 | security | yes | secrets scan, IAM, supply chain, SLSA assess |
| `platform.reliability.*` | 8 | sre | yes | SLO, error budget, capacity, incident |
| `platform.finops.*` | 9 | finops | yes | allocation, unit economics, costing |
| `platform.lab.*` | 14 | lab | yes | scenario run/eval on tiers L0–L4 |
| `platform.k8s.analyze` | 6 | kubernetes | yes | manifest analyzers (PF-K8S-*) |
| `platform.iac.analyze` | 5 | iac | yes | Terraform/OpenTofu config/plan/state |
| `platform.iac.diff` | 5 | iac | yes | plan/state diff |
| `platform.gitops.drift` | 7 | gitops | yes | ArgoCD/Flux desired↔observed |
| `platform.cicd.analyze` | 7 | cicd | yes | GH Actions/GitLab CI/Jenkins/Tekton |
| `platform.observability.map` | 8 | observability | yes | OTel-semconv correlation into graph |
| `platform.platform.maturity` | 11 | platform_product | yes | 5-aspect assessment |
| `platform.platform.scorecard` | 11 | platform_product | yes | per-service scorecards |
| `platform.platform.golden-path` | 11 | platform_product | yes | golden-path model + gaps |
| `platform.backstage.import|export` | 11 | platform_product | yes | catalog projection adapter |
| `platform.integrate|detach` | 13 | adapters | yes | host files (claude/codex/devin/copilot) |
| `platform.capability.*` | 13 | core | yes | manifest, list, describe |
| `platform.forge.manifest` | 15 | integrations | yes | The Forge capability negotiation |
| `platform.forge.delegate` | 15 | integrations | yes | A2A-ready envelope + receipts |

`platform.*` is a namespace, not a runtime requirement: every entry is
implemented locally, offline-capable unless marked otherwise.
