# Forge Audit — spark-forge-aws & api-forge (main, 2026-10-06)

Purpose: separate *generic Forge capability* (reuse/inspire) from *domain-specific*
capability (reimplement for Platform Engineering). Audited at
`/home/edgar/Documentos/projetos/forjas/{spark-forge-aws,api-forge}`.

## spark-forge-aws (0.5.0, pkg `sparkforge_aws`, CLI `sparkforge-aws`)

- **Deps**: PyYAML + jsonschema only; `boto3`, `mcp`, `pyarrow` as optional extras
  behind `require_*()` guards. Core never imports provider SDKs or MCP.
- **Facts**: anchored observations with `fact_id`, `kind`, `source`, `location`,
  `observed`, `attrs`, `measures`, `provenance`, `freshness`. Facts carry no judgment.
- **Findings**: `finding_id`, `rule_id`, `severity`, `status`, non-empty `evidence`
  list of `fact_id` — invalid by construction when empty.
- **Rules**: `rules/catalog/*.yaml` with `rule_id` (SF-AREA-NNN), `action:` block in a
  closed vocabulary gated both directions; `expected_gain` refused by schema.
- **Economy**: ledger, model router, provider_cost, recall, decision plane (shadow
  mode, content-addressed receipts under `.sparkforge/decision-receipts/`),
  `economy report` with `detail_level_effect` measured not claimed.
- **CodeIntel**: 9 code tools backed by a local index (search/symbol/path/context…),
  incremental fingerprinted refresh, 100% recall-by-name floor enforced by script.
- **SDD**: in-repo phases explore→define→design→plan→build→ship; artifacts in
  `docs/sdd/<FEATURE>/`; `sdd check` gate + `sdd stamp` (hash cascade).
- **Agents**: 14 coordinators in `agents/*.md`, 5 executors in `agents/executors/`,
  mirrors generated for `.claude/agents`, `.agents/agents`; `playbook` is the
  dispatch-free floor on Codex/Copilot CI. Routing lives in `rules/catalog/routing.yaml`
  — coordinator choice is data, not judgment.
- **Referee/debate**: `arbitrate` can return `debate.unresolved` + `debate_plan`;
  closure belongs to the referee, never the session.
- **Knowledge freshness**: `knowledge_freshness.py`, `knowledge_drift.py`,
  `knowledge/` tree keyed by domain; versioned rule catalogs (SF-*).
- **Domain-specific (do NOT port)**: Spark/Glue/EMR/Iceberg/Athena extractors and
  rules, DPUSeconds economics, Glue versioning matrix.

## api-forge (0.1.0, pkg `src/apiforge`, CLI `apiforge`/`apiforge-mcp`/`apiforge-tui`)

- **Deps**: pydantic, typer, PyYAML, tree-sitter(+langs), python-hcl2, graphql-core,
  cryptography; `boto3`/`mcp`/textual/rich optional. Core has no provider SDK imports.
- **Case/persistence**: `.apiforge/case/` persisted cases; `next-step` routing after
  findings; Outcome Brief handoff shape.
- **Refusals**: every refusal carries an `AF-*` code + `field` + `unlock`, cataloged
  in `docs/catalog-contract.md`.
- **TaskSpec**: sealed task contracts govern dispatch; sandbox executes; Verifier
  decides. Dynamic parallelism only for independent sealed tasks with budgets.
- **Capabilities**: `src/apiforge/capabilities` manifest; `dispatch` module;
  `apiforge agents sync` renders host mirrors (`.claude/agents`, `.agents/agents`,
  `.codex/agents/*.toml`) from `agents/*.md` single source — mirrors are generated,
  never hand-edited.
- **Economy**: `context compact` (RTK-style), `agentops workflows` (Caveman-inspired),
  `economy report` = measured bytes + transcript-backed tokens only; `evidence gate`
  before any live source.
- **Change control**: `af-change-bundle/1` replay contract; read-only GitHub adapter;
  only a dedicated CI job can open PRs; receipts for external calls.
- **Domain-specific (do NOT port)**: API-IR, OpenAPI/AsyncAPI/GraphQL/gRPC machinery,
  datastore/broker access IRs, contract-evolution rules.

## Generic Forge capabilities → adopted as first-party Platform Forge subsystems

| Capability | Platform Forge home |
|---|---|
| Fact/Finding/Refusal contracts + evidence tiers | `platformforge/models`, `core` |
| Content hashing + artifact store | `platformforge/core` |
| Rule catalog (YAML, executable, versioned) | `rules/catalog`, `platformforge/rules` |
| Knowledge freshness | `platformforge/knowledge`, `knowledge/` |
| TokenSave-style context economy | `platformforge/tokensave` |
| RTK-style output compaction | `platformforge/rtk` |
| Caveman-style output compression | `platformforge/caveman` |
| SDD lifecycle + hash cascade + gates | `platformforge/sdd` |
| Graphfy-style graph + provenance | `platformforge/graph` |
| Economy engine + token ledger + routing | `platformforge/economy`, `routing` |
| Capability registry → CLI/MCP parity | `platformforge/capabilities` |
| Agents single-source + generated mirrors | `agents/`, `platformforge/adapters` |
| Sandbox + receipts + change control | `platformforge/sandbox`, `receipts` |
| Lab / evals / fixtures discipline | `platformforge/lab`, `evals`, `evals/` |

## Reuse decision

- **Conventions & contracts**: adapted, not copied (different domain; MIT-licensed
  sibling projects by the same author — provenance recorded in `SOURCES.md`).
- **python-hcl2**: reused as a dependency for Terraform/HCL parsing (same choice as
  api-forge) — parsing HCL by hand is error-prone and adds no product value.
- **No runtime dependency** on either Forge; no circular imports between Forges.
