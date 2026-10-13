# Cycle 4.1 — Baseline (§2 audit of real main)

| Field | Value |
|---|---|
| HEAD SHA | `0aee5c6f30a9daa60b47d19abce4dd1f78a7dd05` |
| test count | 587 collected |
| eval count | 56 cases (56 pass / 0 fail / 0 unresolved) |
| lab count | 28 scenarios |
| ops action count | 26 typed actions |
| executor count | 6 (git, terraform, tofu, argocd, kubernetes, observe) |
| ops test files | 16 |
| files touching rollback | 7 |
| files touching approval/policy | 18 |
| validation gates | 14 (lint, tests, provenance, linkage, knowledge, packs, lab, evals, coverage, mcp-parity, docs, security, package, self) |
| remote CI state | `.github/workflows/ci.yml` exists; **remote execution = externally_blocked** (no run evidence recorded — never claim remote green) |

## Confirmed blockers (§3–§130 of the prompt)

| # | Gap confirmed in main |
|---|---|
| 1 | `rollback_action` alone — inverse action without captured params (e.g. `kubernetes.scale → kubernetes.scale` reuses *forward* replicas; `terraform.apply_saved_plan` would re-apply the **same** saved plan as "rollback") |
| 2 | `expected_delta` can be empty on mutating plans — verify has nothing to check |
| 3 | ops validation implicit inside generic `tests` gate — no `ops-*` gates |
| 4 | ROADMAP does not reflect Cycle 4/4.1 |
| 5 | `Approval.signature` is a sha256 content seal, not signer identity — terminology overclaims |
| 6 | rollback status not feeding risk/autonomy gates |
| 7 | rollback trigger is a vague convergence string — no typed evidence payload |
| 8 | source-of-truth `conflicted` does not block mutation automation |
| 9 | provider-direct resolution allowed without explicit human-review flag |
| 10 | operation store / locks honesty — local-only scope not documented as such |
| 11 | opgraph edges cite receipts but no completeness validation |
| 12 | receipt fields not canonicalized (operation_id/stage/hashes/actor/policy…) |
| 13 | runbook rollback params cannot reference captured `pre_state` |
| 14 | golden-path ops contracts — verify same contract stack used |
| 15 | auto-rollback lab coverage thin (one scenario) |
