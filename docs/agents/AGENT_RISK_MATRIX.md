# Agent Risk Matrix

Router V2 signals that escalate a route.

## Risk inputs

| Signal | Effect |
|---|---|
| `risk: high` or `blast_radius` above fanout budget | adds operations-safety reviewer |
| `security_sensitive` | adds security reviewer (mandatory) |
| `production` | critical-review mode; change coordinator; human gate intent |
| `conflict`/`comparison` | debate mode (bounded) |
| `mutability: production` | refuses direct dispatch — returns governed-action plan |
| `evidence incomplete` | route proceeds, verdict capped at `unresolved` |
| `fleet scope` | fleet coordinator; whole-fleet context bound enforced |

## Access tiers

`read-only` (most) · `state-writer` (orchestrator + coordinators —
run state only) · `host-adapter` (never in core).

## Model tiers

`deterministic` (executors, guardian) · `fast` (spec reviewer,
synthesizer) · `standard` (specialists, coordinators) ·
`critical-review` (verifier, critic, referees, evidence/security/ops
reviewers).

## Mandatory reviewers by route

- `critical-review`: operations-safety + security + verifier.
- `coordinated`: domain reviewers per domain + verifier.
- `debate`: critic + referee + verifier after resolution.
- `single-specialist`/`multi-specialist`: verifier only.

## Never list (all agents)

Mint evidence · self-verify as sole verifier · mint human approval ·
escalate own autonomy · mutate production · emit raw secrets ·
exceed declared budgets · delegate outside `delegates_to`.
