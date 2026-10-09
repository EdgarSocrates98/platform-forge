# CONTRIBUTING — working on Platform Forge

## Setup

```bash
pip install -e ".[dev]"     # or: uv sync && uv pip install -e .
platformforge doctor --deep # env + workspace + manifest + index health
```

## Gates (run what your change touches)

```bash
uv run pytest -q                     # unit/integration (820 tests)
uv run ruff check .                  # lint — the enforced gate
uv run pytest tests/test_docs_drift.py   # CLI ↔ docs parity (incl. generated surface)
uv run platformforge lab run-all     # Forge Lab scenarios (45)
uv run platformforge evals run       # eval corpus (93 cases)
uv run platformforge evals coverage  # rule ↔ case coverage
uv run platformforge evals precision # measured FP rate
uv run platformforge capability list # registry ↔ CLI ↔ MCP parity
uv run platformforge agents lint     # AgentSpec contract lint (41 agents)
uv run platformforge agents check    # host-mirror drift gate
uv run python scripts/validate.py    # full 40-gate suite → receipt
```

CI runs pytest + ruff + a wheel-install smoke (`platformforge doctor`,
`--help` in a clean env) + all gates in `scripts/validate.py` mirrored
as steps. Match it before pushing.

## Invariants — do not break these

1. T6/T7 inference never becomes a `Fact`; a `Finding` without
   `fact_id` evidence is invalid by construction.
2. `planned ≠ observed ≠ declared ≠ inferred` — keep the distinction
   through facts, edges, findings, receipts.
3. Secrets never cross facts, context packs, Caveman output, or MCP
   responses — redaction happens at the boundary (ADR-0005).
4. Unknown is `unresolved` with an unlock — never zero, never low-risk,
   never a hedged sentence.
5. No provider SDK, no LLM SDK, no network call in core. `collect` is
   dump-only. Mutation is host-side behind an explicit gate.
6. No invented numbers — performance/cost/token claims need a measured
   baseline (`bench`, `economy qpt`).
7. Refusals carry a named code + `unlock`, exit code ≥ 2.

## Add a rule

1. Edit `rules/catalog/<domain>.yaml` — `rule_id`, `domain`, `severity`,
   `title`, `sources:` (registry IDs from `knowledge/sources.yaml`),
   `applies_to`, `when`, optional `versions:` + `remediation`.
2. Run `evals coverage` — the rule needs ≥1 case/scenario.
3. Add an eval case (`evals/cases/<id>/`) with variant
   positive/negative/boundary/version as applicable.

## Add an analyzer

1. `platformforge/<domain>/…` — emit `Fact`s with correct `tier`,
   `source`, `location`, `attrs`.
2. Wire into `analyze` dispatch (`cli/main.py`), `collect` sniffing, and
   `mcp/tools.py` (`_analyze` map) for parity.
3. Add lab scenario + eval case; document in CAPABILITIES.md + the
   domain doc.

## Changed a parser/verb?

`docs/CLI-SURFACE.md` is generated — run
`uv run python scripts/gen_cli_surface.py --write` and commit it with
the change; `test_docs_drift` fails on stale bytes.

## Add an eval case

`evals/cases/<id>/case.yaml`:

```yaml
id: my-case
analyzer: k8s           # _ANALYZERS domain key
type: golden            # see EVALS.md for all 15 types
variant: positive       # positive|negative|boundary|unresolved|version
versions: {kubernetes: "1.29"}   # for version-gated rules
expect:
  rules_fired: [PF-K8S-002]
  rules_not_fired: [PF-K8S-001]
```

Fixture files live in `evals/cases/<id>/fixture/`.

## Add a Lab scenario

`lab/scenarios/<id>/fixture/` + `expected.yaml` (findings matched by
rule prefix). `lab run <id>` compares expected vs observed.

## Add an agent

1. Add an `AgentSpec` v2 entry in `platformforge/agents/roster.py` —
   `when_to_enter`/`when_not_to_enter`/`never` are mandatory; executors
   never delegate; only orchestrator/coordinator roles hold
   non-read-only access; an agent can never be its own verifier.
2. If it's routable, register it in `rules/catalog/routing.yaml` —
   `agents-routing` gate fails on dangling names.
3. `platformforge agents sync` regenerates the five host-mirror
   targets; `agents check` must stay clean (never hand-edit mirrors).
4. Tests: `tests/test_agent_*.py`; evals: `evals/cases/agent-*/`.
   Doc: `docs/agents/AGENT_*_MATRIX.md`.

## Add a skill

Skills live in `.devin/skills/platformforge-<domain>/SKILL.md` —
frontmatter (`name`, `description` with triggers *and* non-triggers),
a canonical verb block, and a discipline section citing invariants and
`PF-*` refusals. Register it in `AGENTS.md` and in the
`platformforge-core` routing section.

## Non-trivial changes → SDD

The repo has a native SDD lifecycle: `platformforge sdd
discover/define/contract/design/plan/build/verify/review/ship` with hash
cascade gates. Use it for features; it's skipped for typo/comment fixes.

## Commit discipline

Commit per wave/feature. Message = *why*, not *what*. Never commit
secrets; `analyze secrets` runs on the diff-sensitive paths anyway.
