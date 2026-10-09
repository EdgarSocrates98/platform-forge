# CYCLE 2 — FINAL MATRIX (§186)

Status vocabulary: `implemented` (works, tested) · `validated`
(evidence-backed by evals/lab) · `partial` · `foundation` · `planned`.

## Capability truth matrix

| Area | Status | Evidence |
|---|---|---|
| Facts T0–T7, T6/T7 barred | implemented | `models/base.py` `__post_init__`, wave tests |
| Planned≠observed provenance | implemented+validated | ADR-0004, graph tests, `analyze drift` |
| Rule provenance 100% | implemented+validated | `catalog_provenance_report` coverage=1.0 |
| Version-aware rules | implemented+validated | ADR-0007, `version` evals, `--versions` |
| Secrets never cross boundary | implemented+validated | ADR-0005, security property tests |
| Real `--detail-level/--offline/--strict` | implemented | `_emit` bounding, central strict, offline guard |
| docs-drift CLI↔docs | implemented | `test_docs_drift.py` |
| Graphfy graph + diff V2 semantic | implemented | semantic categories w/ `fact_ids` |
| Blast radius by impact class | implemented | `graph blast` |
| TokenSave packs v2 (graph/delta/evidence) | implemented | `economy`, `context pack` |
| Quality-per-token measured | implemented | `economy qpt`, `bench tokens` |
| Knowledge registry + freshness + linkage | implemented+validated | `knowledge`, 100% linked |
| Cloud common model + AWS dumps | implemented+validated | `analyze cloud-aws`, T1 facts |
| Azure / GCP dumps | partial | common model, fewer analyzers |
| K8s depth (helm/kustomize/gateway/cilium/auto) | implemented+validated | Wave-E rules + evals |
| GitOps depth (AppSet/AppProject/Flux) | implemented+validated | `analyze gitops` |
| Delivery graph + cross-repo inferred edges | implemented | `cross_repo_edges` provenance=inferred |
| Golden paths + maturity v2 + scorecards | implemented | ADR-0010, `product` |
| SRE/Observability v2 (OTel/SLO/PM/DR/alerts) | implemented | `observe` verbs |
| FinOps v2 (FOCUS, unit, multi-format, insights) | implemented | `finops` |
| Security v2 (IAM paths, Kyverno, SLSA, Cosign) | implemented+validated | `security`, `graph identity-*` |
| Risk v2 (unknowns degrade, not safety) | implemented | `risk` |
| Change review v2 (sandbox→findings→risk→validation) | implemented | `change review` — read-only |
| Eval corpus 34 + coverage 63/63 + precision | implemented+validated | `evals` |
| Lab profiles + chaos + safety contract | implemented | `lab`, `--allow-profile`/`--allow-prod` |
| Capability contracts v2 + negotiation | implemented | `capability check/describe` |
| Referee v2 (6 axes) | implemented | `agents/referee.py` |
| Ownership + contradictions | implemented | `analyze ownership/contradictions` |
| Receipts v2 (sources+cost) | implemented | `core/receipts.py` |
| Explain / Recommend v2 | implemented | `explain`/`recommend` |
| Remediation plan DAG | implemented | `plan` `platformforge.remediation/v2` |
| Execution/security boundaries | implemented+validated | refusal tests |
| Doctor --deep | implemented | `doctor --deep` |
| Bench run/tokens (measured) | implemented | `bench` |
| MCP parity (27 tools, bounded, redacted) | implemented | `mcp/registry.py` |
| Live cloud collectors | planned | out-of-core by design |
| Lab L1–L4 real runtimes | foundation | profile guard + contract exists |
| Multi-cluster/multi-tenant federation | planned | ROADMAP |
| Production-ready certification | — | not claimed; Beta is honest |
