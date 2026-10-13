# Cycle 4.1 — FINAL REPORT
Operational Correctness, Rollback Integrity & Closure

Status: **implemented + closure-validated**
Baseline: Cycle 4 (`0aee5c6`) — Cycle 4.1 commits `4d898c9`..`20a030d`+.

## What changed (by wave)

| Wave | Deliverable | Evidence |
|---|---|---|
| A | Main audit + BASELINE.md | `docs/cycle4.1/BASELINE.md` |
| B–E | `RollbackMaterial` (immutable, hash-bound, CAS `MaterialStore`); RollbackPlan v2 (strategy/status/materials); `ExpectedDelta` mandatory for mutating plans (`PF-OPS-NO-DELTA`); `unknown_dimensions`; `verification_coverage` (no vacuous converge); per-action rollback builders registry; engine wires material capture + material-built rollback | `ops/material.py`, `ops/rollback_builders.py`, `ops/rollback.py`, `ops/engine.py`, `ops/envelope.py`, `ops/models.py` |
| F–G | Source-of-truth conflict captured in material + risk escalation; provider-direct observed state → manual-only; rollback status feeds risk (non-executable raises risk → dual-human); `signature`→`integrity_seal` (tamper evidence, not signer auth; deprecated alias kept) | `ops/risk.py`, `ops/approval.py`, `ops/engine.py` |
| H–J | Eight `ops-*` validation gates + `self` gate + CI workflow; opgraph completeness — edges cite ledger entry hashes, envelope hash, approval `subject_hash`, per-step receipts, material hashes; `validate_projection()`; runbook safe `from:` refs (allowlisted roots, no eval) + `PF-OPS-RUNBOOK-BAD-REF`/`REF-MISSING`; `PlatformRequest.to_change_intent()` (Golden Path uses governed contracts) | `scripts/validate.py`, `.github/workflows/ci.yml`, `ops/opgraph.py`, `graph/vocab.py`, `ops/runbook.py`, `goldenpath.py` |
| K | 5 rollback lab scenarios (scale, annotate, gitops, terraform, impossible) + `trigger_rollback` + rollback expectations in opslab; 12 eval cases + `ops-invariant` probes (material tamper, seal tamper, no-delta, SoT conflict, plan reuse, blind inverse, builders, unknown rollback) | `lab/scenarios/ops-rollback-*.yaml`, `ops/opslab.py`, `evals/ops_invariants.py`, `evals/cases/ops4*` |
| R1–R6 | 18 adversarial tests: hash-bound material, seal≠signature, vacuous verification, approval bounds/actor-kind, rollback FSM/human escalation/no-rerun, plan-reuse refusal | `tests/test_ops_adversarial41.py` |
| L | ROLLBACK.md, APPROVALS.md, EXECUTION.md, VERIFICATION.md, RUNBOOKS.md + OPS/ROADMAP/CHANGELOG/CLI-REFERENCE/CAPABILITIES/DOMAIN-MAP/EVALS updates + closure artifacts | this file, `FINAL-MATRIX.md`, `VALIDATION-RECEIPT.md` |

## Bugs found by the closure process (not by luck)

- `RollbackMaterial.payload()` aliased live mutable fields — `to_dict()` mutation could corrupt the hash. Fixed with deepcopy; adversarial test proves tamper now changes the hash.
- Kubernetes annotate could not express remove-only rollback (added-key case) → `PF-OPS-ANNOTATE-EMPTY`. Executor now supports remove-only sets.
- Rollback fixtures initially approved the wrong elevation — surfaced that `manual-only`/`impossible` correctly escalates to `dual-human`.
- `ruff` caught `re.M/re.I` alias + unused vars during the wave.

## Explicitly NOT done (spec-mandated exclusions)

No new cloud executors; no full Azure/GCP ops; no distributed control
plane; no SaaS server; no policy marketplace; no generic ITSM; no
autonomous production healing; no A6; no broad agent roster; no large
MCP surface (ops MCP remains prepare-only).

## Honest limits

- `integrity_seal` is tamper evidence — signer authentication is out
  of scope and documented as such.
- `requires-replan` rollback (terraform/tofu) never reuses a saved
  forward plan; a new plan must be produced — the operation waits.
- Verification is observation-bound: environments without collectors
  produce `unknown`, never a claimed `converged`.
