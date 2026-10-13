# Cycle 5.1 — Agent Benchmarks

`platformforge agents bench` — compares routing strategies over the
fixed task set. **Honesty label:** all numbers below are *projected*
costs derived from Router V2 output (fanout × budget class), not
measured model spends — real runs are recorded in the run ledger for
future calibration (`measured: projected` in output).

## Strategy comparison (projected)

| Task | Mode | Agents | Budget class | DAG stages | Verifier |
|---|---|---|---|---|---|
| aws-security | single-specialist | 4 | small | 5 | yes |
| incident | coordinated | 5 | deep | 6 | yes |
| fleet-optimization | critical-review | 7 | deep | 8 | yes |

## What the projection shows

- Simple deterministic tasks route to **zero agents** — the cheapest
  correct answer is the verb itself.
- Single-domain tasks route to one specialist + verifier, not a swarm.
- Fanout grows only with domain count and risk — never because "more
  agents" is fashionable.
- Critical-review is the most expensive route by design: 3 reviewers
  + coordinator + verifier.

## What is deliberately not claimed

- No quality comparison (multi-agent vs single-agent correctness) is
  asserted — that requires real run rows; the bench reports the
  machinery needed to measure it (`measured: projected`).
- No token totals are extrapolated from projection to production cost.

## Gates

`agents-evals` — 10 routing/economy eval cases; `agents-independence` —
A1–A12 adversarial probes; all enforced per-commit.
