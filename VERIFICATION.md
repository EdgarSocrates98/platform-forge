# VERIFICATION — observed evidence, never exit codes (Cycle 4 + 4.1)

Verification compares the **declared ExpectedDelta** against
**observed state** across time windows — plus an SLO gate. A command
that succeeded proves nothing about the world.

## ExpectedDelta — `ops/models.py`

`adds`, `removes`, `changes`, `unknown_dimensions` (cycle 4.1).
Every mutating plan must declare one of:

- a non-empty delta, or
- explicit `unknown_dimensions` (honest "we can't predict this axis").

Otherwise `mint_envelope` refuses `PF-OPS-NO-DELTA`. Read-only steps
(validate/show/observe/diff) are exempt.

## Windows

`immediate` → `stabilization` → `extended`. Each window's observed
delta is tokenized (`side:dim:id`) and compared:

- `pass` — every expected token matched, none unexpected;
- `fail` — missing or unexpected tokens;
- `unknown` — no observation for the window (never treated as pass).

## SLO gate

`slo_contract` (error_rate_max / burn_rate_max / budget) vs observed
`metrics`. Missing inputs → `unknown`, violations → `fail`.

## Convergence

| Verdict | Meaning |
|---|---|
| `converged` | all windows pass + SLO pass/unknown + sufficient coverage |
| `partially-converged` | mixed pass/fail/unknown |
| `not-converged` | delta never materialized |
| `regressed` | delta materialized but SLO gate failed |
| `unknown` | insufficient observation |

**Verification coverage (cycle 4.1):** `verification_coverage`
reports expected/matched/missing token counts + ratio per window.
A mutating plan that would be `converged` on an empty/insufficient
delta is downgraded to `unknown` — vacuous matching is never a pass.

`regressed` feeds `finalize_verify` → `rollback-planned`; from there
the material-built rollback plan decides what can actually run
(ROLLBACK.md). Rollback has its own verification
(`restored|partially-restored|regressed|unknown`) — command success
is never claimed as restoration.
