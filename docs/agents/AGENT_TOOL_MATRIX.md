# Agent Tool Matrix

`allowed_tools` / `allowed_verbs` / `allowed_capabilities` per agent —
enforced at dispatch (`agents-contract` gate lints the roster).

## Executors (deterministic tier)

| Executor | Engine wrapped | Verbs |
|---|---|---|
| pf-inventory | collector | `inspect`, `collect` |
| pf-extractor | extractor | `collect`, `analyze` |
| pf-judge | rules engine | `judge`, `policy check` |
| pf-graph-builder | graph builder | `graph *` |
| pf-reconciler | reconciler | `diff`, `analyze drift` |
| pf-simulator | simulator | `change review` (simulate) |
| pf-synthesizer | context composer | `context`, `compress` |
| pf-verifier | verification engine | `verify` |

Executors run on the `deterministic` model tier (no LLM needed), have
`max_tool_calls` ≤ 16, and may not delegate.

## Specialists / reviewers

`standard`/`critical-review` tiers; read-only access; `allowed_verbs`
limited to inspection verbs (`inspect`, `collect`, `analyze <dom>`,
`graph *`, `judge`, `explain`, `diff`, `impact`). No mutation verbs
(`change apply`, `ops run`) appear in any agent spec — production
mutation is host-side only.

## Coordinators

`state-writer` access limited to run state (`.platformforge/runs/`),
never to target infrastructure. `max_parallelism` bounds fanout:
incident 4, change 3, fleet 6, optimization 6, product 3.

## Refusal surface

Any tool outside the matrix → `PF-AGENT-TOOL` refusal with the unlock
instruction naming the host-side path.
