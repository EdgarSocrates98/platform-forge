# Agent Skill Matrix

Domains each agent may claim; routing matches on these (`routing.yaml`).

| Agent | Domains |
|---|---|
| platform-orchestrator | all (dispatch only) |
| platform-planner | all (plan only) |
| platform-incident-coordinator | incident, runtime, sre |
| platform-change-coordinator | change, ops |
| platform-fleet-coordinator | fleet |
| platform-optimization-coordinator | capacity, finops, optimization |
| platform-product-coordinator | dx, golden-paths, product |
| platform-iac-specialist | iac, terraform |
| platform-kubernetes-specialist | helm, k8s |
| platform-gitops-specialist | cicd, gitops |
| platform-sre-specialist | capacity, incident, otel, slo, sre |
| platform-finops-specialist | finops |
| platform-security-specialist | security |
| platform-graph-specialist | graph |
| platform-aws-specialist | aws, cloud |
| platform-crossplane-specialist | crossplane |
| platform-fleet-specialist | fleet |
| platform-policy-specialist | governance, policy |
| platform-capacity-specialist | capacity, reliability |
| platform-product-specialist | dx, product |
| platform-ai-infra-specialist | ai, gpu |
| platform-federation-specialist | federation |
| platform-evidence-reviewer | evidence |
| platform-debate-referee | conflicts |
| platform-operations-safety-reviewer | change, ops |
| platform-security-reviewer | security |
| platform-architecture-reviewer | architecture |
| platform-privacy-reviewer | privacy |
| platform-task-spec-reviewer | tasks |
| platform-adversarial-critic | plans |
| platform-verifier | closure |
| platform-release-guardian | release |
| platform-economy-reviewer | economy |
| pf-inventory | inventory |
| pf-extractor | extract |
| pf-judge | rules |
| pf-graph-builder | graph |
| pf-reconciler | drift |
| pf-simulator | simulate |
| pf-synthesizer | compose |
| pf-verifier | proof |

The `agents-contract` gate fails if a routed name is absent from this
matrix or if a specialist claims a domain outside its entry.
