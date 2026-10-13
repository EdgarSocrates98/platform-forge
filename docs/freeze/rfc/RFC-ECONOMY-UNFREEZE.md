# UNFREEZE RFC — Economy Control Plane (prompt_evo_economy.md)

> An unfreeze request is a FeatureException with `decision` and this
> document attached as evidence. Companion exception:
> `docs/freeze/exceptions/FE-002.json`.

## 1. Trigger

- [x] new required platform paradigm — **Economy Control Plane**:
  `prompt_evo_economy.md` (owner-authored spec, 298 sections) directs the
  evolution of Platform Forge's economy-aware architecture into a unified
  Economy Control Plane: budget envelopes, multilayer cache, context
  gateway, checkpoint/resume, reconciliation, provider pricing, routing
  scorecards — none of which is covered by a current pillar's contract
  (they exist as fragmented primitives, not a control plane).

## 2. Evidence

- `real_world_blocker`: the agentic runtime spends context/agents without
  a unified plan, receipt, or reconciliation. `economy/engine.py`,
  `tokensave/`, `live/budget.py`, `agents/runledger.py` each measure a
  fragment; there is no EconomyPlan, no unified BudgetEnvelope, no
  decision-receipt chain, no cache dependency graph, no checkpoint/resume
  of spend. The DoD questions ("what did this run cost? why this context?
  how much did we reuse?") cannot currently be answered with receipts.
- Existing capability insufficient: `economy report` reports a token
  ledger only; there is no `cache stats|invalidate|gc`, no
  `context capsule|expand|delta`, no `economy checkpoint|resume|
  reconcile|doctor|explain`, no `routing explain|compare|scorecard`.
- Alternatives considered: (a) keep fragmented primitives + document
  limits — rejected: leaves the DoD questions unanswerable; (b) copy
  API/Spark Forge internals — rejected by spec §6 (adapt, don't copy:
  Platform has fleet/live/graph needs they don't); (c) implement per
  spec §276 phase order — chosen.

## 3. Blast radius

- New schemas (additive, v1): `economy-plan/v1`, `budget-envelope/v1`,
  `cache-entry/v1`, `cache-receipt/v1`, `context-capsule/v1`,
  `checkpoint/v1`, `reconciliation/v1`, `provider-pricing/v1`,
  `routing-decision/v1`, `routing-scorecard/v1`, `waste-finding/v1`.
  No frozen schema is migrated; existing ledgers stay append-compatible.
- Agents: no roster delta. New per-role budgets attach to existing
  `AgentContextPack`/run ledger. Routing gains profiles and scorecards;
  champion/challenger stays shadow + human-gated promotion.
- Control planes: new `economy/controlplane.py` (plan→budget→cache→route→
  account→checkpoint→reconcile→report) coordinating existing engines.
- Review surface: `platformforge/economy/`, `context/` (new), `routing/`,
  `tokensave/`, `live/`, `agents/`, `cli` groups `economy|context|cache|
  routing`, MCP read-only economy surface, ~10 new validation gates.

## 4. Rollback

All new surfaces are additive modules + CLI subcommands; rollback is
`git revert` of the phase commits. Ledgers are append-only JSONL —
new fields are optional, old readers ignore them. Caches are
content-addressed under `.platformforge/` — deleting the directory is a
full rollback of cached state. No production mutation path is touched.

## 5. Decision

`approved` — owner directive via `prompt_evo_economy.md` (explicit
instruction: "faça absolutamente tudo do prompt_evo_economy.md"), date
2026-04-24, evidence: `prompt_evo_economy.md`, `FE-002.json`,
`docs/economy-parity/BASELINE.md`, `docs/economy-parity/GAP-MATRIX.md`.

After completion: re-freeze per `prompt_evo_economy.md` §298 —
"return to Architecture Freeze & Real-World Dogfooding"; the freeze
manifest is regenerated so new surfaces land in the manifest.
