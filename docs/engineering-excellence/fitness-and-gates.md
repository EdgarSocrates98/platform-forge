# Engineering Excellence — Platform Fitness

## Existing authority

Platform Forge owns ops/live, agents, economy, graph, UI, analytics and token saving. Its `GLOSSARY.md`, `CAPABILITIES.md`, ADRs, evals and tests remain source of truth.

## Gate map

| Gate | Evidence | Federated projection |
|---|---|---|
| deterministic validation | `tests/`, contract tests, CI | descriptor `deterministic` |
| risk planning | agent/risk/economy tests | operation class + limitations |
| blast radius | ops/live and architecture docs | evidence refs + next action |
| graph integrity | graph packages and tests | graph capability + receipt ref |
| economy | economy/token tests | measured cost or `unknown` |
| UI status | `portal/`, UI tests | host/portal support state |

## Fitness rules

- Architecture fitness checks observed invariants, not aesthetic preference.
- High-risk mutation needs explicit policy and verification.
- Missing graph, cost or host data stays unknown.
- Token saving cannot reduce required evidence.
- Router receives Platform specialty only when contract matches.
- The Forge may project status; Platform retains execution authority.

## Verification

```text
python -m pytest tests -q
python -m ruff check .
```

Run targeted suites for agent routing, economy, graph, ops/live, contracts and portal before changing shared contracts.

## Pending

- Export descriptor projection from Platform manifest.
- Add architecture-fitness receipt with invariant ids and blast-radius scope.
- Publish benchmark baseline by risk class and host mode.
