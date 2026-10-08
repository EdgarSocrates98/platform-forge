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
| 2.1 Closure | single-source validation (`scripts/validate.py` = CI), version tri-state, canonical source ids, QPT measured==delivered, Crossplane families+Upbound, knowledge packs, wheel self-contained, adversarial review fixes (H1–H3) | validated | 13 gates green; see `docs/cycle2.1/FINAL-MATRIX.md` |

Declared gaps (not hidden):

- Lab L1–L4 real runtimes (containers/kind/cloud) — profiles declared and
  guarded; host execution stays host-side.
- Live cloud collectors — dumps only; `collect` never calls provider APIs.
- QPT default judge is facts-only (packs carry facts essential-complete);
  file-body judgment needs a custom judge — labeled in every receipt.
- MCP tools don't take `--versions`; version-gated rules resolve to
  `unresolved` over MCP (safe direction).
- Knowledge packs are a seed corpus (4 domains, 13 packs) — thin by
  design, expansion is normal-cycle work.
- Redaction markers are a prefix oracle for low-entropy secrets
  (documented in SECURITY.md).

## Cycle 3 — implemented

Runtime & live platform intelligence — delivered (see LIVE.md +
docs/cycle3/FINAL-REPORT.md): observation envelopes + store + cursors,
host-side kubectl/aws collectors (read-only allowlists), multi-layer
temporal graph (v2), identity resolution, desired↔planned↔observed↔
runtime reconciliation, runtime topology (OTel/Hubble/EndpointSlice),
cluster federation, live drift journal, incident intelligence V3,
safe remediation planning (never applies), live capability surface +
MCP. Core stays SDK-free/network-free; transports are the only
network boundary.

## Cycle 4 — validated

Governed operations control plane (OPS.md): intent → plan → simulate →
risk → policy → approval → envelope → execute → verify →
converge/rollback. A4 autonomy target; typed actions only; hash-bound
approvals; append-only op store; 10+ ops-* lab scenarios; ops-* eval
corpus; MCP `platformforge_ops` (prepare-only, never executes).

## Cycle 4.1 — implemented

Operational correctness, rollback integrity & closure (ROLLBACK.md,
docs/cycle4.1/):

- **RollbackMaterial** — immutable, content-addressed pre/post-state
  capture for every mutating step; hash-bound; provenance tiers.
- **RollbackPlan v2** — material-built strategy/status
  (`executable|requires-replan|manual-only|impossible|unresolved`);
  "rollback ready" only when executable; Terraform forward plans are
  never reverse plans (`PF-OPS-PLAN-REUSE`).
- **Rollback execution** — typed trigger, same locks + idempotency,
  rollback preconditions (drift → human review), failure → `failed` +
  human escalation, never automatic second rollback.
- **Rollback verification** — restored/partially-restored/regressed/
  unknown from post-state vs captured pre-state; `rc=0` is never
  `restored`.
- **ExpectedDelta gate** — mutating plans refuse minting without a
  declared delta or explicit `unknown_dimensions` (`PF-OPS-NO-DELTA`);
  verification coverage blocks vacuous `converged`.
- **Integrity seal** — `signature` → `integrity_seal` (tamper evidence,
  not signer authentication; deprecated alias preserved).
- **ops-* validation gates** — 8 new gates in `scripts/validate.py`,
  mirrored as CI steps.
- **opgraph completeness** — edges cite exact ledger receipts,
  material hashes, approval subject_hash; `validate_projection()`
  reports orphans/gaps.
- **Runbook safe refs** — `{from: pre_state.x}` binding, allowlisted
  roots, no eval.
- **5 new rollback lab scenarios + 12 eval cases + R1–R6 adversarial
  suite** (`tests/test_ops_adversarial41.py`).

## Cycle 5 — implemented

Enterprise platform intelligence & fleet scale (FLEET.md,
PLATFORM-ANALYTICS.md, OPTIMIZATION.md, FEDERATION.md, ENTERPRISE.md,
docs/cycle5/):

- **Fleet contracts** — `Fleet`/`FleetMember`/`FleetSnapshot`/
  `MemberObservation`; identity `kind:canonical_id`; coverage is
  first-class in every answer.
- **Organizational Graphfy** — 8 layers, `organizational` impact
  class (ownership ≠ blast radius); pluggable `GraphBackend`
  (memory + SQLite).
- **HistoryEngine** — unified event sources, strict windows,
  `HistoricalPattern` with support/confidence; correlation never
  causality.
- **Analytics engines** — measurement by dimension, golden-path
  adoption/friction/escapes, policy intelligence (evidence-gated
  false-positive candidates), FinOps V4 (hierarchy/trend/anomaly/
  rightsizing/idle/unit-economics), capacity+saturation risk,
  reliability hotspots (centrality ≠ criticality), ops analytics,
  DX metrics (team-level only — no individual scoring).
- **OptimizationEngine** — opportunity → recommendation (honest
  uncertainty, suppressed stays visible) → `plan()` emits a
  `ChangeIntent` and **nothing else** — the Cycle 4 pipeline still
  governs (§303).
- **Federation** — `NodeManifest` + classified `export_summary`
  (fail-closed, secrets always denied) + `federated_query`;
  intelligence crosses, authority never does.
- **AI platform awareness** — GPU/MIG pools, serving detection,
  denominator-required unit economics.
- **SQLite analytics store** — retention GC, right-to-forget,
  secret-refusal; config schema v3 (features + privacy pins).
- **Lab + evals** — `lab/fleets/acme` shared fixture, 11 fleet
  scenarios, 14 invariant probes; adversarial E1–E12 suite
  (`tests/test_fleet_adversarial.py`).
- **CLI** — `fleet`, `analytics`, `optimize`, `ai`, `federation`
  namespaces (read-only); `optimize plan` is the only bridge and it
  emits a ChangeIntent doc.
- **11 `fleet-*`/`adversarial` validation gates** mirrored as CI
  steps; `platformforge bench scale` measured benchmarks.

## Cycle 5.1 — frozen (agentic runtime)

Bounded, evidence-first agent orchestration on the deterministic core
(docs/agents/, docs/cycle5.1/):

- **AgentSpec v2** — canonical 41-agent roster (orchestration 7,
  coordinators 5, specialists 15, reviewers 6, executors 8) with
  entry/exit conditions, delegation boundaries, reviewers, verifier,
  `never` list; JSON schemas for spec/task/handoff/run/debate.
- **Router V2** — extended signals (risk, blast, security, production,
  evidence completeness, mutability, fleet scope, conflict) → modes
  `deterministic|single-specialist|multi-specialist|coordinated|
  debate|critical-review` + instantiated DAG + budgets; dangling
  agent names are a build failure (`agents-routing` gate).
- **Bounded debate** — 2 specialists + critic + referee, 1–3 rounds,
  evidence-cited positions only; referee emits winner/tied/unresolved
  over 10 axes + receipt; verifier still closes the loop.
- **Agent economy** — `Task → Graph scope → Evidence → ContextPack`;
  budget classes (tiny→critical), charge-before-spend, exhaustion =
  `partial` not silent success; delta context via previous-hash;
  run ledger persists calls/bytes/tools/fanout/duration/reuse.
- **Host mirrors** — 205 generated files over `agents/`, `.agents/`,
  `.claude/`, `.codex/`, `.devin/`; `agents check` drift gate;
  `agents playbook` gives zero-subagent hosts the same evidence +
  verifier requirements.
- **Independence** — producer is never sole verifier
  (`PF-AGENT-INDEPENDENCE`); critical routes add operations-safety +
  security reviewers; no mutation verbs in any spec.
- **Scale** — graph diff ~154× at 5k nodes (SCC condensation + bitset
  ancestor cones); 10k-node/500k-edge measured; unattempted sizes
  return `unsupported-on-host`.
- **Soak** — analytics store schema v2 + migration chain +
  retention GC + right-to-forget + vacuum; deterministic replay proves
  restart/crash/forget invariants.
- **Gates** — 7 `agents-*` gates (contract/routing/mirrors/economy/
  debate/independence/evals) in `scripts/validate.py` + CI.
- **Architecture freeze** — `FREEZE-REVIEW.md` READY; new capability
  requires explicit unfreeze (ADR-0052).

## Architecture Freeze — in progress

Stability & real-world validation (prompt_evo_freezing.md,
docs/freeze/): freeze manifest + contract snapshots
(`freeze manifest|snapshot|check`), feature-exception governance,
golden+holdout replay corpus (`.platformforge/cases/`), FP/FN ledgers,
routing/context audits, measured scale + soak receipts, self/cross-Forge
dogfooding, security review, release hardening. **No Cycle 6 feature
expansion** — unfreeze requires an RFC (docs/freeze/UNFREEZE-RFC.md).

| Phase | Deliverable | Status | Gate |
|---|---|---|---|
| STABILITY | contracts snapshotted; breaking changes gated; maintenance-mode releases only | active | `freeze-contracts`, `freeze-replay`, `freeze-docs`, `freeze-exceptions` |
| DOGFOODING | self + cross-Forge runs feed REAL-WORLD-ISSUES.md; every issue → evidence → fix | active | regression test per fixed issue |
| REAL-WORLD VALIDATION | replay corpus grows from real cases; read-only production pilot (observe → recommend → prepare → governed mutate) | active | `cases replay` green; pilot receipts |
| KNOWLEDGE MAINTENANCE | monthly source freshness, quarterly compatibility sweep, release-triggered review | active | `knowledge check|drift`, KNOWLEDGE-REVIEW.md |
| COMMUNITY | sanitized public cases → regression fixtures; operator feedback (useful/incorrect/already-known/unactionable/missing-context) → review, never direct rule training | planned | feedback → issue → evidence → fix |

Definition of done per feature: contract, implementation, tests, negative test,
unresolved behavior, evidence, docs, source provenance, eval, CLI/MCP exposure.
