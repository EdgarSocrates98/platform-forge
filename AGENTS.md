# AGENTS — working in this repository

Platform Forge is a deterministic, offline-first platform-intelligence
tool. Agents working here follow the sibling-forge contract:
**run the verb before answering about an artifact** — do not read a file
when a verb answers the question.

## Question → verb

| Question about | Verb |
|---|---|
| repo artifacts / posture | `inspect`, `collect`, `analyze <dom>` |
| rule verdicts | `judge`, `policy check`, `explain` |
| dependencies / impact | `graph deps/blast/paths`, `impact` |
| what changed | `diff`, `analyze drift` |
| secrets / IAM / supply | `analyze secrets/iam/sbom/supply`, `graph identity-*` |
| cost | `finops costs/ingest/unit/report` |
| SLO / incident / telemetry | `observe slo/incident/otel`, `correlate` |
| a proposed change | `change review`, `risk` |
| capability surface | `capability list/describe/check`, `forge manifest` |
| a repo under `workspace.yaml` | `analyze <dom> --repo <member>` |

Cite the `fact_id` / `rule_id` that backs the answer. If the verb returns
`unresolved` or a `refusal`, report that — do not fill the gap.

## Repo contract

- Offline core: no provider SDK, no LLM SDK, no network in
  `platformforge/`. Adapters are the only mutation/IO boundary.
- Facts carry evidence tiers; findings carry evidence + sourced rules.
- `planned ≠ observed`; contradictions surface both states.
- Redaction is a boundary pipeline — never emit raw secrets.
- Budgets never cover safety/evidence/`unresolved` reporting.
- Every refusal must preserve a `PF-*` code + `unlock` instruction.

## Gates before commit

```bash
uv run pytest -q && uv run ruff check .
uv run pytest tests/test_docs_drift.py
uv run platformforge lab run-all && uv run platformforge evals run
```

Non-trivial work goes through the in-repo SDD: `platformforge sdd
discover → define → contract → design → plan → build → verify → review →
ship` (see SDD.md, CONTRIBUTING.md).

## Agent surfaces

Canonical roster: `platformforge/agents/roster.py`. Host mirrors are
generated — `.claude/agents/`, `.agents/agents/`, `.codex/agents/` —
via `platformforge agents sync`; never edit a mirror, lint with
`agents lint`.

Skills that dispatch work here live in `.devin/skills/platformforge-*`
(core, change, economy, finops, graph, lab, sdd, security, sre). The
`platformforge-core` skill routes an ambiguous request to the right
domain skill.

## Boundaries

- `change approve|apply` and any production mutation: refused in core —
  host-side only, behind an explicit policy gate.
- Lab non-static profiles / prod chaos: refused without the explicit
  opt-in flags (`--allow-profile`, `--allow-prod`).
- No automatic PRs, pushes, credential use, or destructive ops.
