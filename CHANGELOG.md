# CHANGELOG

All notable changes. Format: wave/feature, the "why", key commits.

## [Unreleased] — Cycle 2 (truth + depth hardening)

### Added
- **Truth hardening** — `planned` provenance (T2 plans no longer promote
  to observed), rule→source provenance (100%), version-unresolved
  semantics, real `--detail-level/--offline/--strict`, docs-drift gate,
  CI workflow. (`72ad365`)
- **Economy v2** — graph-aware/delta context packs, evidence classes,
  measured quality-per-token, ledger v2 (`payload_bytes`). (`e9e9c48`)
- **Knowledge engine** — source registry contract, freshness/drift
  check, rule↔source linkage gate.
- **Cloud common model** — AWS/Azure/GCP dump analyzers → T1
  provider-observed facts; dump-only, no SDK in core. (`40f698c`)
- **K8s depth** — Helm, Kustomize, Gateway API, Cilium/Hubble flows,
  VPA/KEDA/Karpenter, ArgoCD/Flux depth, Rollouts, delivery graph.
  (`c42d56c`)
- **Platform product** — golden-path engine, maturity v2 (observed vs
  declared, `overclaimed`), scorecards v2 (9 axes). (`d11e22e`)
- **SRE v2** — OTel semconv, SLO multi-window burn, incident v2,
  postmortem, DR, prometheus/grafana.
- **FinOps/Security v2** — FOCUS 1.0 validation, unit economics,
  multi-format billing ingest, IAM v2 (trust/SCP/boundary/OIDC/identity
  paths), Kyverno/SLSA/Cosign, risk v2, `change review` pipeline.
  (`26b2a40`)
- **Lab/Eval expansion** — 15 eval types, corpus 9→34, coverage report
  (63/63), measured precision, 4 lab profiles with `--allow-profile`
  guard, chaos on the graph. (`ca0333a`)
- **Hardening sweep** — capability contracts v2 + negotiation, referee
  v2 (6 axes), `ownership.conflicted`/`state.contradiction`, cross-repo
  inferred edges, `doctor --deep`, `bench`, receipts v2, `explain`/
  `recommend` v2, `plan` remediation/v2 DAG, MCP parity. (`f4d58bc`)
- **Docs wave** — 7 ADRs (0004–0010), 7 domain docs (KNOWLEDGE, RULES,
  SECURITY, EVALS, CLOUD, GOLDEN-PATHS, QUALITY-PER-TOKEN), cycle-2
  final reports. (`df544fe`)

### Fixed
- `GraphBuilder` treated T2 (generated plan) as `observed` — now `planned`.
- Precision measurement didn't propagate declared `versions` → measured
  false FP rate; the gate now catches it.
- Caveman compress (incl. mode `off`) and MCP responses redact before
  output — boundary-level, not per-tool.
- `PF-SLO-002` unreachable condition (burn≥1 ⇔ exhausted) — keyed on
  burn_rate semantics.

### Docs
- `GLOSSARY.md`, `CLI-REFERENCE.md`, `MCP.md`, `CONTRIBUTING.md`,
  `AGENTS.md`, `docs/README.md`, README.pt-BR synced.

## Cycle 1 — initial surface

Initial release: deterministic core (facts/findings/refusals/receipts),
TokenSave/RTK/Caveman economy kernel, Graphfy graph, domain analyzers
(IaC/k8s/GitOps/CI-CD/observability/FinOps/security), SDD lifecycle,
Forge Lab, MCP surface, agent roster + host mirrors.
