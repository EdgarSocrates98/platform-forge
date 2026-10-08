# Cycle 4.1 — VALIDATION RECEIPT

Commands run on the final tree; evidence, not claims.

## Full gate sweep — `uv run python scripts/validate.py`

| Gate | Verdict |
|---|---|
| tests (`pytest -q`) | pass — 600+ tests, 0 failures |
| lint (`ruff check .`) | pass |
| docs (`test_docs_drift`) | pass |
| lab (`lab run-all`) | pass — 32 scenarios, 0 failures |
| evals (`evals run`) | pass — 68 cases, 0 fail / 0 unresolved |
| eval coverage | 63/63 rules |
| ops-contracts | pass |
| ops-approval | pass |
| ops-execution | pass |
| ops-rollback | pass |
| ops-verification | pass |
| ops-policy | pass |
| ops-evals | pass |
| ops-lab | pass |
| self (dogfooding) | pass |
| package | pass |
| security | pass |
| provenance | pass |
| linkage | pass |
| knowledge | pass |
| packs | pass |
| mcp-parity | pass |
| coverage | pass |

## Focused evidence

- `pytest -q tests/test_ops_adversarial41.py` — 18/18
  (hash tamper, seal tamper, vacuous-verify, bounds, actor-kind,
  rollback FSM/escalation/no-rerun, plan-reuse refusal).
- `platformforge lab run ops-rollback-terraform` → `requires-replan`
  (forward-plan reuse refused `PF-OPS-PLAN-REUSE`).
- `platformforge lab run ops-rollback-impossible` → `manual-only`,
  risk escalated to R5 → `dual-human` required.
- `platformforge lab run ops-rollback-scale` → `rolled-back` +
  `restored` via post-rollback observation.

## Known limitations (carried into ROLLBACK.md/VERIFICATION.md)

- `integrity_seal` = tamper evidence; signer authentication is a
  declared non-goal (APPROVALS.md).
- `requires-replan` rollbacks wait for a new plan — never execute a
  stale forward plan.
- `unknown` verification is reported as `unknown`, never upgraded.
