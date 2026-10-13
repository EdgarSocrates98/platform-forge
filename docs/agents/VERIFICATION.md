# Verification

`platformforge/agents/verifier.py` — independent closure of agentic
runs.

## Independence rule

The producer of a result can never be its sole verifier.
`verify_run` refuses (`PF-AGENT-INDEPENDENCE`) when the verifier set
equals the producer set. A coordinator dispatching work cannot mark
that work verified.

## What the verifier checks

- Evidence requirements from the sealed TaskSpec are met.
- Every `supported`/`contradicted` finding cites evidence.
- Required reviewers ran; required gates ran.
- Router-declared verifier is the agent that ran.

## Verdicts

`verified` — all gates + evidence requirements met.
`unresolved` — evidence missing or checks incomplete (honest, not a
fail).
`refused` — independence violated, verifier bypass attempted, or a
mandatory gate skipped.

## After debate

A referee `winner` verdict resolves the disagreement only — the
verifier still re-checks decisive evidence independently. Referee
resolution never substitutes for verification.

## Budget exemption

Verification and unresolved-reporting are never cut by budgets —
a run that can't afford verification ends `unresolved`, not `done`.
