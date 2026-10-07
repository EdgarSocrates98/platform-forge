# ROADMAP — executable phases

§130 — status vocabulary (never "complete" because a file exists):

| Status | Meaning |
|---|---|
| `planned` | scoped, not started |
| `foundation` | models/contracts landed, thin behavior |
| `partial` | real behavior for part of the surface; gaps declared |
| `implemented` | full surface wired; not yet eval-validated |
| `validated` | eval corpus + gates pass against it |
| `production-ready` | validated + soak/review evidence |

| Phase | Deliverable | Status | Gate |
|---|---|---|---|
| 0 Discovery | docs set, ADRs, source registry, contracts | validated | docs exist, sources cited |
| 1 Deterministic core | models, facts, findings, refusals, provenance, hashing, artifact store, receipts, store GC | validated | unit + schema tests, goldens, offline |
| 2 Economy kernel | tokensave v2 (graph-aware packs, delta), rtk, caveman (redact-first), routing, ledger v2, quality-per-token | validated | economy eval baseline, recall floor |
| 3 SDD | lifecycle artifacts, hash cascade, gates, verbs | implemented | gate refuses stale/missing evidence |
| 4 Graphfy | node/edge+provenance (observed/planned/declared/inferred), snapshots, diff v2, blast classes, cross-repo | validated | graph correctness + determinism evals |
| 5 IaC | Terraform/OpenTofu config+plan+state, drift, module pinning | validated | fixtures + version-gated rules |
| 6 Kubernetes | manifests PF-K8S-*, Helm/Kustomize, Gateway API, Cilium/Hubble, autoscaling, version-gated deprecation | validated | positive/negative/boundary/unresolved/version fixtures |
| 7 GitOps/CI-CD | ArgoCD (multi-source/AppSet/AppProject/waves), Flux, GH Actions, CI security | validated | same fixture discipline |
| 8 Observability/SRE | OTel semconv, SLO multi-window burn, incident v2, postmortem, DR, prom/grafana, capacity | validated | slo.unresolved honored |
| 9 FinOps | cost facts, FOCUS 1.0 validation, unit econ, ingest (CUR/Azure/GCP/OpenCost/Kubecost), insights | validated | no unit mismatching |
| 10 DevSecOps | policy, IAM v2 (trust/SCP/boundary/OIDC/chaining), identity paths, redaction, SBOM, SLSA, Kyverno, Cosign | validated | redaction never leaks |
| 11 Platform product | catalog, golden path engine, maturity v2, scorecards v2 (9 axes), Backstage | validated | unknown ≠ zero |
| 12 Agents/skills | coordinators, referee v2 (6 axes), routing table | implemented | agents call real engines |
| 13 MCP/host parity | 27 tools from registry v2, host files, integrate/detach | validated | CLI≡MCP semantic tests |
| 14 Forge Lab | L0 static + profiles (container/kubernetes/cloud guarded), chaos on graph, eval corpus 34 cases, coverage 63/63, precision | validated | scenarios produce expected findings |
| 15 Forge interop | manifest v2, capability negotiation, delegation, A2A envelope, receipts | implemented | no coupling |
| 16 Hardening | CI wheel install, offline test, capability contracts, bench, docs parity | implemented | full suite + push |

Declared gaps (not hidden):

- Lab L1–L4 real runtimes (containers/kind/cloud) — profiles declared and
  guarded; host execution stays host-side.
- Live cloud collectors — dumps only; `collect` never calls provider APIs.

Definition of done per feature: contract, implementation, tests, negative test,
unresolved behavior, evidence, docs, source provenance, eval, CLI/MCP exposure.
