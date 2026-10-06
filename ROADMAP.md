# ROADMAP — executable phases

| Phase | Deliverable | Gate |
|---|---|---|
| 0 Discovery | this docs set, ADRs, source registry, contracts | docs exist, sources cited |
| 1 Deterministic core | models, facts, findings, refusals, provenance, hashing, artifact store, receipts, source registry | unit + schema tests, goldens, offline |
| 2 Economy kernel | tokensave, rtk, caveman, context engine, routing, ledger | economy eval baseline, recall floor |
| 3 SDD | lifecycle artifacts, hash cascade, gates, verbs | gate refuses stale/missing evidence |
| 4 Graphfy | node/edge+provenance, build, queries, diff, blast radius | graph correctness evals |
| 5 IaC | Terraform/OpenTofu config+plan+state, drift, graph conv. | fixtures + version-gated rules |
| 6 Kubernetes | manifest analyzers PF-K8S-*, Helm/Kustomize, Gateway | positive/negative/boundary/unresolved fixtures |
| 7 GitOps/CI-CD | ArgoCD, Flux, GH Actions, CI security | same fixture discipline |
| 8 Observability/SRE | OTel corr., SLO engine, error budget, incidents, capacity | slo.unresolved honored |
| 9 FinOps | cost facts, allocation, unit econ, graph costing | no unit mismatching |
| 10 DevSecOps | policy, IAM graph, redaction, SBOM, SLSA, supply chain | redaction never leaks |
| 11 Platform product | catalog, golden paths, maturity, scorecards, Backstage | unknown ≠ zero |
| 12 Agents/skills | coordinators, specialists, reviewers, referee, routing table | agents call real engines |
| 13 MCP/host parity | tools from registry, host file generation, integrate/detach | CLI≡MCP semantic tests |
| 14 Forge Lab | tiers L0–L4, scenario framework, bundled scenarios | scenarios produce expected findings |
| 15 Forge interop | manifest, delegation contracts, A2A envelope, receipts | no coupling |
| 16 Hardening | security, perf, economy evals, offline install, docs parity | full suite + push |

Definition of done per feature: contract, implementation, tests, negative test,
unresolved behavior, evidence, docs, source provenance, eval, CLI/MCP exposure.
