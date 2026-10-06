# ECONOMY — token & context economy design

Principle: **correct, verifiable, reproducible results at minimum token cost —
measured, never claimed.**

## Execution order (cheap deterministic first)

```text
cache → parser → index → rule → graph → local composition
      → cheap model (if needed) → strong model (if needed)
      → multi-agent (only when justified)
```

## TokenSave (`platformforge/tokensave`)

- **Content addressing**: sha256 of files, sections, symbols, facts, graphs,
  command outputs, doc fragments. Unchanged content is never re-read.
- **Incremental context**: `baseline + delta + affected neighborhood`, never
  `full repo × N`.
- **Search index**: SQLite FTS5; literal/regex/symbol/path/type/fact/rule/node/
  edge queries; incremental rebuild. No mandatory embeddings.
- **Context packs**: minimal `{task, relevant_files, relevant_symbols, facts,
  findings, graph_neighborhood, rules, sources, budget}`.
- **Ranking**: task terms + changed files + symbols + graph distance + rule refs
  + ownership + runtime + risk + historical findings.
- **Dedup**: same evidence/stack/log block/manifest is included once.
- **Budget**: `input_budget`, `output_budget`, `reasoning_budget`,
  `tool_budget`. Insufficient → `refuse | reduce scope | escalate`. Essential
  evidence is never silently dropped.
- **Ledger**: per run — requested/delivered/reused/skipped/compressed context,
  provider tokens when observed, estimates when estimated, cache hits/misses.
  States distinguished: `observed | estimated | unknown`.

## RTK (`platformforge/rtk`)

Command-output intelligence: parse `git`, `pytest`, `terraform`, `kubectl`,
`helm`, `argocd`, `trivy`, `checkov`, cloud CLIs → structured
`{exit_code, summary, errors[], warnings[], changed[], interesting[], omitted,
raw_artifact}`. Raw output lives in the artifact store; the agent consumes the
compact form and can `expand(error_id|section|lines)` lazily. Never loses error
codes, resource IDs, file:line, exit status, security warnings, failed
assertions.

## Caveman (`platformforge/caveman`)

Output compression modes `off | lite | full | auto`. Compress language, never
substance: commands, paths, identifiers, exceptions, security warnings, policy
failures, IAM actions, ARNs, technical URLs, evidence, fact/rule IDs, numbers,
units, versions are protected spans. `auto` picks by context (info → full,
architecture → lite, incident/destructive → prose). Every compression emits a
receipt: before/after chars+tokens, protected spans, ratio.

## Quality-per-token

Metric combines correctness, evidence recall, finding recall, false-positive
rate, latency, token cost, money cost. An economy change passes only when
quality stays above gates — measured by `evals/` suites comparing
`baseline_context` vs `tokensave_context` on the same cases.

## Claims discipline

Banned without benchmark: "saves 60%", "30% faster", unquantified promises.
Required form: `hypothesis + expected direction + benchmark required`.
