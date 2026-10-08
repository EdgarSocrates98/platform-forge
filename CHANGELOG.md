# CHANGELOG

All notable changes. Format: wave/feature, the "why", key commits.

## [Unreleased] — Cycle 5.1 (Bounded Agentic Runtime)

Agents become operators of the deterministic engines — bounded,
evidence-cited, independently verified, budgeted, and replayable.

### Added
- `agents/` — AgentSpec v2 canonical roster (41 agents):
  orchestration core (orchestrator, planner, task-spec-reviewer,
  verifier, adversarial-critic, debate-referee, release-guardian),
  5 coordinators, 15 domain specialists, 6 reviewers, 8 executor
  subagents (`pf-*`) wrapping deterministic engines.
- Contracts — `PlatformTaskSpec` (sealed, evidence requirements
  mandatory), `AgentHandoff`, `AgentRunEnvelope` (charge-before-spend
  budgets), `RunRecord`, `Debate`; JSON schemas in `contracts/`.
- `routing/router.py` — Router V2: extended signals → modes
  (`deterministic` … `critical-review`) + instantiated DAG + budgets
  + mandatory reviewers + verifier; `validate_routing()` fails on any
  dangling agent name.
- `agents/coordinators.py` — bounded fanout dispatch (`max_parallelism`
  3–6), closed `delegates_to`, run-state write scope only.
- `agents/specialists.py` — structured finding contract; evidence-less
  `supported`/`contradicted` demoted to `unsupported` mechanically.
- `agents/reviewers.py` — checklist reviewers (evidence, security,
  ops-safety, architecture, privacy, economy).
- `agents/verifier.py` — independent closure; producer can never be
  sole verifier (`PF-AGENT-INDEPENDENCE`).
- `agents/debate.py` — bounded debates (2+1+1, 1–3 rounds),
  no-evidence positions refused, referee emits winner/tied/unresolved
  over 10 axes + receipt.
- `agents/contextpack.py` + `economy/` — `Task → Graph scope →
  Evidence → ContextPack`; budget classes tiny→critical; delta
  context via `previous_hash`; run ledger under
  `.platformforge/runs/` with resume preserving spent budget.
- `agents/mirrors.py` — generated mirrors for `agents/`, `.agents/`,
  `.claude/`, `.codex/`, `.devin/` (205 files); `agents check`
  reports missing/stale/stray.
- `agents playbook` — zero-subagent fallback carrying identical
  evidence + verifier requirements.
- `graph/diff.py` + `graph/query.py` — SCC condensation + memoized
  bitset ancestor cones; ~154× faster diff at 5k nodes;
  `bench scale` measures 10k-node/500k-edge configs and reports
  `unsupported-on-host` beyond host budget.
- `analytics/store.py` — schema v2 + declared `_MIGRATIONS`,
  `(subject,kind)` index, `vacuum()`; `analytics/soak.py` —
  deterministic replay measuring insert/query/forget/GC/vacuum +
  restart + crash rollback + migration replay.
- Evals — 10 agent cases (`simple-iac-single-specialist` …
  `host-no-subagents`); adversarial A1–A12 suite
  (`tests/test_agent_adversarial.py`).
- Validation — 7 `agents-*` gates (contract/routing/mirrors/economy/
  debate/independence/evals) in `scripts/validate.py` + CI; 40 gates
  total.
- Docs — `docs/agents/` (11), ADRs 0041–0052, `docs/cycle5.1/`
  closure artifacts (baseline, reports, benchmarks, soak, freeze).

### Changed
- `routing.yaml` → v2 canonical names (6 previously-dangling names
  fixed).
- Referee contract expanded to 10 decision axes.
- `AgentSpec` v1 → v2; `LEGACY_NAMES` preserves old ids.

### Boundaries (unchanged, reasserted)
- Agents never mutate production, mint evidence, mint approval, or
  self-verify; `change approve|apply` stays host-side (`PF-OPS-*`).
- Unsupported scale targets return `unsupported-on-host` — never
  extrapolated.

## [Unreleased] — Cycle 5 (Enterprise Platform Intelligence, Fleet Optimization & Organizational Scale)

The north-star question — "how is the whole org platform behaving,
where are the biggest problems, and where should we invest?" —
becomes answerable with evidence. Optimization produces governed
ChangeIntents; it never executes.

### Added
- `fleet/` — Fleet/FleetMember/FleetSnapshot/MemberObservation
  contracts (`platformforge/fleet/v1`), org-graph projection
  (8 layers, `organizational` impact class), `loader.py` shared
  fleet-dir loader, 9 deterministic fleet questions.
- `analytics/` — HistoryEngine (strict windows, support-confidence
  patterns), measurement by dimension, golden-path analytics,
  policy intelligence (evidence-gated false-positive candidates),
  FinOps V4, capacity/saturation risk, reliability hotspots
  (centrality ≠ criticality), ops analytics, DX metrics
  (team-level only), debt, SQLite `AnalyticsStore` (retention GC,
  `forget_subject`, secret-refusal).
- `optimize/` — OptimizationEngine + `scan_fleet` opportunity
  generator; honest uncertainty; suppressed stays visible;
  `plan()` → `ChangeIntent` is the only bridge (§303).
- `federation/` — NodeManifest, fail-closed FederationPolicy,
  `export_summary` (secrets denied at every classification),
  `federated_query` (node-local answers).
- `aiplat/` — GPU/MIG pools, serving detection, denominator-required
  unit economics (`ai workloads|gpu|economics`).
- `graph/backend.py` — pluggable GraphBackend (memory + SQLite).
- CLI namespaces: `fleet`, `analytics`, `optimize`, `ai`,
  `federation` — all read-only, fleet-dir inputs.
- Config schema v3 — `features` flags (`federation` opt-in) +
  `privacy` pins (dx team-level-only, person ids forbidden,
  right-to-forget); migration 0→1→2→3.
- `platformforge bench scale` — measured graph/store benchmarks.
- Lab: `lab/fleets/acme` shared fixture + 11 `fleet-*` scenarios;
  14 invariant probes (`evals/fleet_invariants.py`);
  `tests/test_fleet_adversarial.py` (E1–E12).
- Validation: 11 new gates (`fleet-*`, `adversarial`) in
  `scripts/validate.py`, mirrored as CI steps.
- 10 top-level docs (FLEET.md … ENTERPRISE.md), 10 ADRs
  (0031–0040), docs/cycle5/ closure artifacts.

### Changed
- `graph/vocab.py` — organizational node kinds/edges + AI platform
  kinds; `EDGE_IMPACT` reports `organizational` separately.
- `fleetlab` uses the shared `fleet.loader`.
- Capability manifest → `platformforge/capability-manifest/v4`.

### Honest limits (declared, not hidden)
- Analytics are deterministic aggregates — no ML claims.
- `fleet drift` on stale inputs returns no fresh patterns by design.
- Federation exchanges intelligence only — never credentials or
  execution authority.

### Cycle 5 polish waves (post-closure)
- `fleet report <dir>` — north-star receipt
  (`platformforge/fleet-report/v1`): coverage, per-dimension findings,
  `invest_next` cited; suppressed kept visible.
- `fleet risks --question Q`, `optimize plan --out <file>`
  (ChangeIntent doc ready for the ops pipeline).
- MCP exposure — 5 read-only tools (`platformforge_fleet|_analytics|
  _optimize|_ai|_federation`, 34 total) closing the declared gap;
  `optimize plan` via MCP can never write files.
- FOCUS validation honesty — `spec_version` pinned to known 1.0–1.4;
  unknown versions refuse (`PF-FINOPS-FOCUS-VERSION`);
  `detect_datasets()` for 1.3/1.4 datasets (detected, not conformant).
- `fleet_report` lab check kind + `fleet-report` scenario
  (44 lab scenarios) + `fleet-report-all-cited` eval probe (83 evals).
- `docs/cycle5/RESEARCH-LEDGER.md` — FOCUS 1.4 / CycloneDX 1.7 /
  SLSA v1.0 findings and explicit non-claims.

## [Unreleased] — Cycle 4.1 (Operational Correctness, Rollback Integrity & Closure)

Correctness and closure pass over Cycle 4: rollback becomes
material-bound evidence work instead of blind inversion, mutating
plans must declare expected outcomes, and approval terminology
stops implying identity proof it doesn't have. See ROLLBACK.md.

### Added
- `ops/material.py` — `RollbackMaterial` (immutable, content-addressed,
  pre/post-state + SoT + limitations) + `MaterialStore` write-once CAS.
- `ops/rollback_builders.py` — per-action registry emitting typed
  rollback actions or replan descriptors; terraform/tofu saved plans
  → `requires-replan` (`PF-OPS-PLAN-REUSE` on reuse attempts).
- `RollbackPlan` v2 — strategy/status/material_hashes/replans/
  limitations; "ready" only when `status == "executable"`.
- `engine.execute_rollback()` — typed trigger, shared locks,
  idempotent repeats, rollback preconditions (drift → human review),
  failed rollback → `failed` + human escalation, §40 receipt.
- `engine.verify_rollback()` — restored/partially-restored/regressed/
  unknown from post-rollback observation vs captured pre-state.
- `ExpectedDelta` enforcement — mutating plans without
  adds/removes/changes or `unknown_dimensions` refuse to mint
  (`PF-OPS-NO-DELTA`); `verification_coverage` downgrades vacuous
  convergence to `unknown`.
- `integrity_seal` — approval seal renamed to honest semantics
  (tamper evidence, never signer authentication); `signature` kept
  as deprecated serialization alias; tampered approvals →
  `PF-OPS-APPROVAL-TAMPERED`.
- SoT conflict handling — `source_of_truth` captured per material;
  rollback status feeds `assess_risk` (manual-only/impossible lifts
  the risk ceiling — `git.push` → R5 → dual-human approval).
- opgraph completeness — edges cite exact ledger entry receipts,
  step receipts + material hashes on `mutates`, `rolled_back_by`
  node/edge; `validate_projection()` reports orphans/gaps.
- Runbook safe refs — `{from: pre_state.x}`/`params.x`/`result.x`
  allowlisted binding, no eval (`PF-OPS-RUNBOOK-BAD-REF`/`REF-MISSING`).
- `PlatformRequest.to_change_intent()` — golden-path provisioning
  uses the same governed contracts; no parallel workflow.
- 8 `ops-*` validation gates in `scripts/validate.py` (+ CI steps):
  contracts, approval, execution, rollback, verification, policy,
  evals, lab.
- Lab: 5 new scenarios (ops-rollback-scale/-annotate/-gitops/
  -terraform/-impossible); runner gains rollback expectations +
  `trigger_rollback`.
- Evals: 12 new cases + `ops-invariant` probe check (tamper, seal,
  delta refusal, SoT conflict, plan reuse, blind inverse, builders).
- `tests/test_ops_adversarial41.py` — R1–R6 adversarial waves.

### Fixed
- `RollbackMaterial.payload()` deep-copies mutable fields — a mutated
  `to_dict()` could previously corrupt the live object's hash.
- `kubernetes.annotate` executor accepts remove-only annotations
  (`key-` form) — required for pure-additive forward changes.

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
- `platformforge ops` CLI — capabilities/config/delegate/intent/plan/
  simulate/risk/policy-eval/runbook/run/store verbs; `ops run` dry-runs
  by default; `--execute` uses host argv-only transports
  (`host_transport()`, never a shell string) behind hash-bound
  approval; results persist to the operation store.
- OPS.md — the Cycle 4 operations reference doc.

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
