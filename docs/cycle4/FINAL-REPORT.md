# CYCLE 4 — FINAL REPORT

Governed Platform Engineering Control Plane — `prompt_evo_cycle4.md`.
Scope: phases A–W executed sequentially; each phase committed; gates
green at every commit. Autonomy target A4 (execute with human
approval); A5 exists only for lab/non-prod reversible experiments; A6
is a declared non-goal.

**Verdict:** Platform Forge can now take a governed change from intent
to verified convergence — under policy, behind hash-bound human
approval, with typed actions only, append-only audit, and derived
rollback — without ever becoming an arbitrary shell agent.

- Tests: **572 pass** (Cycle-3 baseline 411 → +161)
- Evals: **56 pass** (48 → +8 ops cases)
- Lab: **27 scenarios pass** (17 → +10 ops scenarios)
- New surface: `platformforge ops <11 verbs>`; `platformforge/ops/`
  (~4.3k LOC); capability manifest **v3**
- Contracts added: `change-intent`, `change-plan`, `change-event`
  schemas

Commits: `0195213` baseline+ADRs → `a784709` B → `35fa192` C →
`4b23caf` D → `733c91e` E → `b16730b` F → `e1f8c44` G → `f40a022` H →
`fdd51b1` I → `15472d2` J+M → `c0d27ae` K → `12339bc` L → `cf9231b` N →
`d66d5b8` O → `39be024` P+Q → `bd51578` R+S → `942b259` T → `775b2b4` U →
`69a713e` V → `e745ac2` W.

---

## Capability matrix

| Capability | Before (C3) | After (C4) | Implementation | Tests | Evals/Lab | Known gaps |
|---|---|---|---|---|---|---|
| Intent & plan | `live plan` produced remediation suggestions | typed `ChangeIntent`/`ChangePlan` DAG + `ExpectedDelta`, hash-pinned, evidence-required | `ops/models.py`, `ops/engine.py::propose/plan` | `test_ops_models.py` | ops-planning | propose covers known SoT shapes; unknown → `PF-OPS-SOURCE-UNKNOWN` |
| Source of truth | static | resolver: GitOps→git, TF state→tf, Crossplane→XR, Helm→chart | `ops/source_of_truth.py` | models suite | — | unknown signal → unresolved, never guessed |
| Simulation | none | S0–S5 levels, deterministic projection + honest limitation receipts | `ops/simulate.py` | suite | — | S4/S5 are bounded projections, not live cluster twins |
| Risk | §130 finding-risk | R0–R5 per-step, 13 dimensions, unknown≠low | `ops/risk.py` | suite | ops-* | dimensions absent → explicitly `unknown` + escalation |
| Policy | rule catalog | V2: canonical decisions, precedence, deny-overrides, expiring exceptions, shadow `would_*`, adapters fail-closed | `ops/policy.py` | `test_ops_policy.py` | ops-policy-denial | external adapters (OPA/Kyverno) are evaluators-in, no embedded rego |
| Approval | none | hash-bound, TTL, scope, parameter bounds, actor-kind, break-glass, signature tamper check | `ops/approval.py` | `test_ops_approval.py` + property | ops-expired-approval, ops-break-glass | signatures are hash-binding, not PKI identity |
| Operation lifecycle | none | 19-state FSM, append-only hash-chained ledger (redacted), resource locks, idempotent effect-keys, preconditions | `ops/operation.py`, `ops/preconditions.py`, `ops/store.py` | `test_ops_operation.py`, `test_ops_hardening.py` | ops-conflicting-operation, ops-stale-observation, ops-changed-plan-hash | store is file-based; no distributed locking across hosts |
| Typed actions | none | 26-action catalog w/ risk/mutation/dry-run/idempotency/rollback metadata; forbidden verbs refuse `PF-OPS-UNSTRUCTURED` | `ops/actions.py` | `test_ops_executors.py`, property | — | catalog is intentionally narrow; extensions are new typed actions, never raw argv |
| Executors | none (core read-only) | git (PR evidence body), terraform/tofu (saved-plan hash binding + drift precheck), argocd, kubernetes (scale/rollout-restart/annotate), observe; transport injected | `ops/executors/*.py`, `host_transport()` | executor suite + property | ops-replica-drift etc. | executor argv correctness verified against docs; live runs need host tools |
| Envelope | none | `ExecutionEnvelope` binds plan-hash + decisions + approvals + actions; frozen hash | `ops/envelope.py` | suite + property | ops-changed-plan-hash | — |
| Verification | exit-code-level checks | expected↔observed delta across immediate/stabilization/extended + SLO gate; success≠convergence | `ops/verify.py` | suite | ops-verification, ops-bad-rollout | observed inputs are caller-supplied/snapshot-based, not yet polled live in `ops run` |
| Rollback | none | 8 derived strategies + saga compensation; prod never auto-rolls | `ops/rollback.py` | `test_ops_rollback.py` | ops-bad-rollout, ops-partial-failure | non-compensatable steps are named, not faked |
| Auto-remediation | none | 12-check eligibility gate; any unknown → ineligible | `ops/autorem.py` | `test_ops_autorem.py` | — | eligibility ≠ execution — still requires the normal pipeline |
| Runbooks | none | parameterized, hashed, bindable runbooks + 2 builtins | `ops/runbook.py` | `test_ops_runbook.py` | — | builtin library intentionally small; YAML-defined runbooks supported via `from_dict` |
| Golden Path lifecycle | catalog only | `PlatformRequest` staged lifecycle + receipts + readiness score | `ops/goldenpath.py` | `test_ops_goldenpath.py` | — | readiness is heuristic scoring, not a guarantee |
| FinOps/security gates | analyze-time | in-pipeline cost-delta + security gates (IAM/exposure/provenance/vulns) | `ops/gates.py` | goldenpath suite | — | cost delta needs cost facts input; absent → reported, not zero |
| Operational graph | — | ops node/edge kinds, impact class `operation`, receipt-cited evidence | `ops/opgraph.py`, `graph/vocab.py` | `test_ops_opgraph.py` | — | projection is opt-in (`apply_operation_projection`) |
| Cross-Forge | A2A envelope v2 | manifest v3 + delegation contract: intents/plans in, execution authority never out | `ops/registry.py`, `forge/manifest.py` | registry tests | — | negotiation is request validation, not yet a wire protocol |
| Config & store | none | config schema v2 + migrations; append-only operation store + audit digest | `ops/config.py`, `ops/store.py` | `test_ops_hardening.py` | — | — |
| CLI reachability | API-only | `ops` verb family; `ops run` dry-run default, `--execute` host argv transports behind approval | `cli/main.py::cmd_ops`, `_ops_run` | `test_cli_ops.py` (11) | replays all 10 lab specs | — |
| Audit | ledger | ledger tip + store verify + opgraph receipts; every refusal carries `PF-*` + unlock | `ops/store.py::verify` | suite | — | no external audit sink (SIEM export) — file store is the sink |

## Safety invariants — adversarially tested

`tests/test_ops_property.py` + `test_ops_hardening.py` verify:

- forbidden actions (`shell.run`, `kubectl.exec`, `aws.call`, `eval`,
  `execute_anything`) → `PF-OPS-UNSTRUCTURED` at *every* entry point
  (validate, envelope mint, executor dispatch, CLI run);
- agent `actor_kind` cannot satisfy human approval;
- tampered approval signature / wrong subject hash → refusal;
- stale observation, plan-hash drift, active freeze →
  `PF-OPS-PRECONDITION-FAILED`;
- duplicate side-effects skip via `effect_key` (idempotent, recorded
  `skipped: idempotent-duplicate`);
- ledger redaction at append; envelope param redaction on serialize;
- lock conflict → `PF-OPS-LOCK-CONFLICT`, never silent override;
- unknown risk dims escalate, never auto-low;
- dry-run receipts exist without any host call.

## Honest gaps (declared)

1. **Execution transports are argv adapters** — git/terraform/argocd/
   kubectl must exist on the host; `ops run --execute` is the boundary
   and remains gated by approval. No cloud SDK executor exists by
   design.
2. **Verification inputs are snapshots** — `verify` consumes observed
   deltas supplied by the caller/lab; closed-loop re-observation
   (collector → verify in one run) is a natural next step, not yet
   wired in `ops run`.
3. **LEARN is shallow** — `ops/analytics.py` + `ops analytics` now
   aggregate the store (outcomes, rollback rate, failure classes);
   deeper learning (per-action success priors feeding simulation,
   runbook drift detection) remains future work.
4. **Operation store is local** — file-based under
   `.platformforge/operations/`; multi-writer coordination relies on
   `LockTable` in-process only.
5. **A5 lab surface** — `autorem.eligible` gates exist; no scheduled
   autonomous loop ships (and A6 never will).

## Post-delivery adversarial gap-closure (waves X1–X5)

A second audit pass over cycles 1–4 found and closed real defects:

| Wave | Fixes |
|---|---|
| X1 safety | `--offline` refuses live transports; approval parameter bounds enforced; required approval types honored; resource-state + maintenance-window preconditions execute |
| X1b rollback | `execute_rollback` added — `rollback-planned → rolled-back` FSM, `ops rollback` verb, lab auto-rollback |
| X1c reconcile | per-resource-type coverage gating; `#uid`/short-kind normalization; `IdentityResolver` groups expand match keys; conflicts → `identity-drift` |
| X2 reachability | `live changes` (CloudTrail journal + GC + `--events-file`), `graph at`/`graph timeline` verbs |
| X3 LEARN | `ops analytics`, `ops history`, `ops status`, opgraph projections wired into run + `ops graph` |
| X4a audit | `ReceiptWriter` wired into `_emit` — every CLI op emits a receipt; cost/security gates evaluate before policy in `ops run` |
| X4b collect | detection + analyzers for GHA/GitLab CI/Dockerfile/Backstage — no more silent `undetected` |
| X4c tokensave | packs carry `sources`, real `reused_from_previous`, `reduced_scope` vocabulary, `--allow-escalate`, literal/regex/symbol/path/kind search |
| X5a | `knowledge drift` = real drift report; graph gaps gained SPOF + unreachable analysis |
| X5b | `scripts/validate.py` `self` gate (dogfooding); `docs/cycle2.1/CI-VALIDATION.md` honest blocked receipt; `_emit` annotates every refusal with a canonical `pf_code` `PF-*` alias while preserving legacy `platform.*` codes |
| MCP | `platformforge_ops` — prepare-side only; `approve`/execute refuse `PF-OPS-MCP-*` |

## Verification

```
uv run pytest -q                       # 586+ pass
uv run ruff check .                    # clean
uv run pytest tests/test_docs_drift.py # pass
uv run platformforge lab run-all       # 27 scenarios, 0 fail
uv run platformforge evals run         # 56 pass, 0 fail
uv run platformforge evals coverage    # 63/63 rules covered
```
