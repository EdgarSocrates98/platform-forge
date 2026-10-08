# CHANGELOG

All notable changes. Format: wave/feature, the "why", key commits.

## [Unreleased] — Cycle 4 (Governed Platform Engineering Control Plane)

Platform Forge evolves from live intelligence into a governed control
plane: `OBSERVE → UNDERSTAND → DIAGNOSE → RECOMMEND → PLAN → SIMULATE →
GOVERN → APPROVE → EXECUTE → VERIFY → CONVERGE/ROLLBACK → AUDIT → LEARN`.
Target autonomy A4; A5 exists only as lab/non-prod experiments; A6 is a
non-goal. Platform Forge is never an arbitrary shell agent.

### Added
- `platformforge/ops/` — ChangeIntent/ChangePlan/ExpectedDelta models,
  source-of-truth resolution (GitOps→git, TF state→terraform,
  Crossplane→XR layer, Helm→chart/values; unresolved →
  `PF-OPS-SOURCE-UNKNOWN`).
- Risk classes R0–R5 with 13 dimensions + reversibility classes;
  unknown risk is never low risk.
- Policy engine V2 — canonical decisions, receipts, precedence,
  deny-overrides, scoped/expiring exceptions, shadow mode
  (`would_*`), OPA/Kyverno/CEL adapters fail closed to `unresolved`.
- Approval engine — exact-hash binding, scope, TTL, parameter bounds,
  actor/role/kind, break-glass objects, signature tamper detection;
  agent-minted approvals never satisfy human approval.
- Operation FSM (19 states), append-only hash-chained ledger with
  redaction at append, resource locks, idempotency effect-keys,
  safe resume, precondition gates.
- ExecutionEnvelope + typed action vocabulary; `shell.run`,
  `execute_anything`, `aws.call`, `kubectl.exec`, `eval` refused as
  `PF-OPS-UNSTRUCTURED`.
- Executors: git (PR evidence body), terraform/tofu (saved-plan hash
  binding + drift precheck), argocd (GitOps-first), kubernetes (narrow:
  scale/rollout-restart/annotate+resourceVersion), observe.
- Verification engine — ExpectedDelta vs ObservedDelta across
  immediate/stabilization/extended windows + SLO gate; executor
  success ≠ convergence.
- Rollback plans (8 strategies, derived per-action) + saga
  compensation; auto-rollback lab/non-prod only.
- Simulation levels S0–S5 with honest limitation receipts —
  "simulation passed ≠ production safe".
- Auto-remediation eligibility gate (12 checks, any unknown fails).
- Structured runbooks + 2 builtins; PlatformRequest lifecycle FSM;
  readiness scoring (unknown ≠ ready); FinOps CostDelta + security
  gates (IAM/exposure/provenance/vulns, worst-status verdict).
- Operational Graphfy layer — ops node/edge kinds, impact class
  `operation`, receipt-cited evidence; `operation_only()` subgraph.
- Capability manifest v3 — per-action autonomy/mutation/risk +
  cross-forge delegation contract (accepts intents, never execution).
- Forge Lab V4 — 10 ops scenarios (drift, selector, rollout, denial,
  expiry, hash-mismatch, stale-obs, lock-conflict, partial-failure,
  break-glass); 8 ops eval cases.
- `.platformforge/config.yaml` schema v2 + migrations;
  OperationStore (append-only JSONL + hash chain + schema migration +
  audit digest).
- COMPATIBILITY.md, DEPRECATION.md, config.example.yaml.

### Security hardening
- Ledger entries redact secrets at append; envelope serialization
  redacts action params; approvals carry optional hash signatures;
  `check_approval` enforces actor_kind allowlist.

## [Unreleased] — Cycle 2.1 (closure + reproducibility)

Adversarial closure pass over Cycle 2 — every guarantee a reviewer could
attack got tested, and the real ones got fixed. Phases A–H, each a commit.

### Fixed (adversarial review)
- Graph edge merge crashed on `planned` provenance; per-edge provenance
  could launder any tier into `observed`; negative tiers minted observed.
- `versions:` constraints were unvalidated — vacuous/garbage constraints
  produced strong verdicts. Now fail-loud at catalog load; duplicate
  rule_ids rejected; missing catalog dirs warn.
- `--strict` bypassed unresolved on `reliability`/`security` verbs and a
  `[:200]` list cap dropped tail findings.
- Crossplane: `notupbound.io` spoofed the provider suffix; junk specs
  classified as ProviderConfig via `"provider" in group`; empty
  `status.atProvider` counted as evidence; `spec.resourceRefs` minted
  XRs from arbitrary CRDs.
- Redaction: `db_password`/`client_secret`/`aws_secret_key` evaded kv
  patterns (snake_case prefixes); `/+=` value chars truncated AWS
  secrets below the length floor; multi-line PEMs unreachable under
  per-line scanning; MCP artifact store + `rtk expand` persisted and
  returned raw secrets; the MCP redaction test was vacuous.
- QPT measured a payload the pack never delivered (full file bodies,
  path-filtered facts); measured after judging; unresolved→violated
  flips counted as kept; budget refusal crashed the bench.
- `review_change` defaulted to CWD-relative `rules/catalog` — zero-rule
  review outside the checkout; coverage/package gates printed instead of
  asserting; evals gate ignored unresolved verdicts.
- Ledger `token_basis` was free-form and observed counts were
  unfalsifiable — now a closed vocabulary, and observed rows require a
  `transcript_ref`.

### Added
- `scripts/validate.py` — single gate source for local + CI; the
  workflow orchestrates it, no hidden logic.
- `docs/cycle2.1/FINAL-MATRIX.md` + `VALIDATION-RECEIPT.json`
  (machine-readable, sha-stamped).
- `docs/cycle3/PROPOSAL.md` — Cycle 3 concept (runtime/live intel),
  spec only.

## [Released] — Cycle 2 (truth + depth hardening)

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
