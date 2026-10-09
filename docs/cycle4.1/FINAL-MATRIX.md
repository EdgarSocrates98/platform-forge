# Cycle 4.1 — FINAL REQUIREMENT MATRIX

Every spec theme → implementation → verification evidence.

| Spec theme (§) | Requirement | Implemented | Evidence |
|---|---|---|---|
| Rollback material (§B, core) | Capture real pre-state per mutating step, immutable + hash-bound | `RollbackMaterial` + `MaterialStore` CAS, deepcopy payload, receipt `material_hash` | adversarial R1 tests, `ops/material.py` |
| Rollback plan (§B) | Built from material, not blind inverse; honest statuses | `RollbackPlan v2`: executable/requires-replan/manual-only/impossible/unresolved | `ops/rollback.py`, lab `ops-rollback-*` |
| Terraform safety (§B) | Saved forward plan never reused for rollback | `PF-OPS-PLAN-REUSE`; `requires-replan` status | `ops/executors/terraform.py`, eval `ops4-*`, adversarial |
| ExpectedDelta (§E) | Mandatory for mutating ops | `PF-OPS-NO-DELTA` at `mint_envelope`; `unknown_dimensions` escape hatch | tests + evals |
| Verification (§E) | Coverage-bound converge; no vacuous pass | `verification_coverage` per window; empty delta → `unknown` | adversarial R3 tests |
| Source-of-truth (§F) | Conflict → human review / blocks auto | SoT metadata in material; provider-direct → manual-only; conflict feeds risk | `ops/risk.py`, evals |
| Risk/autonomy (§F) | Rollback status feeds risk | non-executable rollback raises risk (R5 → `dual-human` observed in lab) | `ops-rollback-impossible` scenario |
| Approval integrity (§G) | `signature` → `integrity_seal`, honest semantics | seal = tamper evidence only; `PF-OPS-APPROVAL-TAMPERED`; deprecated alias | `ops/approval.py`, APPROVALS.md, adversarial |
| Validation gates (§H) | ops-* gates + CI | `ops-contracts/approval/execution/rollback/verification/policy/evals/lab` + `self` | `scripts/validate.py`, `.github/workflows/ci.yml` |
| Opgraph (§I) | Edges cite receipts/approvals/materials | exact ledger hashes, envelope hash, subject_hash, per-step receipts, material hashes; `validate_projection()` | `ops/opgraph.py`, tests |
| Runbook safety (§J) | Safe `from:` refs, no eval | allowlisted roots `pre_state/params/result`; `BAD-REF`/`REF-MISSING` | `ops/runbook.py`, tests |
| Golden Path (§J) | Same governed contracts | `PlatformRequest.to_change_intent()` | `goldenpath.py`, tests |
| Lab (§K) | 5 rollback scenarios | `ops-rollback-scale/annotate/gitops/terraform/impossible` — 15 ops scenarios, 32 total | `lab run-all` |
| Evals (§K) | Rollback cases + invariant probes | 12 cases + `ops-invariant` (8 probes) — 68 total | `evals run` |
| Adversarial (§R) | R1–R6 questions answered by tests | 18 tests; found real aliasing bug | `tests/test_ops_adversarial41.py` |
| Docs (§L) | Rollback/ops/approvals/exec/verify/runbooks + roadmap/changelog/CLI | ROLLBACK.md (new) + APPROVALS/EXECUTION/VERIFICATION/RUNBOOKS + all updated docs | `test_docs_drift` |

## Prohibitions — verified absent

| Excluded | Verification |
|---|---|
| new cloud executors | `ops/executors/` unchanged count (git/terraform/argocd/kubernetes/observe) |
| distributed control plane / SaaS | no new service code; core offline invariant test green |
| policy marketplace / ITSM / A6 | no such modules; ROADMAP unchanged intent |
| broad agents / large MCP | ops MCP surface still 1 prepare-only tool; `mcp-parity` green |
