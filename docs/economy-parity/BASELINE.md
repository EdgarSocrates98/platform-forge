# Economy Baseline — prompt_evo_economy.md §3–4

HEAD SHA at audit: `999337523edb07473fab7ecdd78315ae9fea9c92` (main, post
Architecture-Freeze maintenance R2). Unfreeze governance: FE-002 +
`docs/freeze/rfc/RFC-ECONOMY-UNFREEZE.md`.

## Existing economy capabilities

| Primitive | File | What it does today |
|---|---|---|
| EconomyEngine | `platformforge/economy/engine.py` | deterministic-first strategy picker (`COST_ORDER`, `STRATEGIES`, capability reqs); `compare()` = champion/challenger **shadow** mode (records projections, never enables); `report()` over TokenLedger |
| ContextEnvelope | `economy/envelope.py` | canonical serializer; `model` vs `deterministic` byte split; measured == evaluated by construction |
| QPT | `economy/qpt.py` | quality_per_token — full vs packed envelopes, same judge, quality floors (finding/evidence recall, precision, unresolved=1.0); verdicts `beneficial|optimization_not_beneficial|no_reduction` |
| QPT bench | `economy/bench.py` | fixed corpus (terraform/k8s/gha-security/iam/incident/change-review) |
| FleetContextPack | `economy/fleetpack.py` | fleet context funnel — bottom-up within budget (org→fleet→clusters→services→neighborhood→evidence) |
| TokenSave index | `tokensave/index.py` | SQLite FTS5, incremental by content hash |
| ContextPackBuilder | `tokensave/packs.py` | graph-aware, explainable, budget-deciding pack assembly |
| Token budget | `tokensave/budget.py` | `check_input_budget` — ok | reduced_scope | escalate | refuse; `min_essential` refuses rather than drops evidence |
| TokenLedger | `tokensave/ledger.py` | append-only JSONL; requested/candidate/selected/delivered/reused/cached/compressed/skipped; essential vs optional; basis closed vocab `observed|estimated|unknown`; observed requires `transcript_ref` |
| RTK | `rtk/compact.py` | tool output compaction |
| Caveman | `caveman/compress.py` | context compression |
| AgentContextPack | `agents/contextpack.py` | bounded agent payload; immutable; follow-up agents get `previous_hash + delta` |
| AgentRunLedger | `agents/runledger.py` | per-run agentic spend: model calls, context/output bytes, tools, fanout, duration, cache reuse, delta bytes |
| Debate | `agents/debate.py` + `referee.py` | bounded (≤4 participants, ≤3 rounds), evidence-required positions, referee adjudication on declared axes, receipt |
| Router V2 | `routing/router.py` | TaskSignal→ mode + coordinator + specialists + reviewers + verifier + DAG + budget class + reasons + fallbacks; routes are data (`rules/catalog/routing.yaml`) |
| ProviderCallLedger | `live/budget.py` | ObservationBudget ceilings enforced inside collectors (objects/events/bytes/api_calls/duration/clusters/accounts/regions/pages); measured call ledger per service |
| Knowledge | `knowledge/{registry,packs}.py` | dated sources, freshness state, knowledge packs |
| Case corpus | `cases/` | 16 replay cases (10 golden + 6 holdout), FP/FN ledgers, route-audit, context-audit |

## Cache capabilities

**No formal economy cache exists.** The TokenSave index is
content-addressed for incremental rebuild, and `economy/engine.py` lists
`cache` as the cheapest cost class, but there is no artifact/fact/graph/
finding/context/analysis/decision cache layer, no dependency
declaration, no selective invalidation, no cache receipt, no GC/stats.

## Context pack capabilities

`tokensave/packs.py` + `agents/contextpack.py`: bounded packs, explainable
selection, delta-via-hash for follow-up agents. Missing: `context://`
refs, ContextCapsule schema, lazy expansion (`context expand`),
sufficiency states, role-specific pack shapes (verifier/critic/debate),
context checkpoint.

## Agent budget capabilities

`AgentContextPack.budget_class` (economy|standard|deep) + run ledger
per-run measurement + router `_budget()`. Missing: unified BudgetEnvelope
dimensions (tool_calls, provider_calls, fanout, wall_time, money), hard
vs soft limits, phase budgets (SDD mapping), per-role budgets.

## Routing capabilities

Router V2 full dispatch decision, shadow `compare()`, route-audit over
the 16-case corpus (fanout 3.38, 0 flags). Missing: routing profiles
(economy/balanced/deep/strict/offline), RoutingRequest/RoutingDecision
canonical contracts, RoutingScorecard, routing receipt with policy
version, decision-plane receipt linking cache+context+routing+verify+
budget decisions.

## Provider-call budgets

`live/budget.py` — ObservationBudget ceilings inside collectors +
ProviderCallLedger. Not unified with the token/agent ledgers (§34).

## QPT benchmarks

`run_qpt_bench()` — 6 fixed tasks, full vs packed envelopes, same judge,
verdicts + receipts. Floors: finding/evidence recall 0.98, precision 0.9,
unresolved 1.0. Not yet QualityPerCost (tools/agents/provider calls/wall
time/money dimensions).

## Known gaps (vs spec §7–298)

1. No `EconomyPlan` contract / explainable plan fields.
2. No unified `BudgetEnvelope` (dimensions, hard/soft, phases, roles,
   protected items).
3. Ledgers fragmented: token / provider-call / agent-run are separate
   JSONL silos — no ONE ECONOMY VIEW.
4. No multilayer cache: no CacheDependency, CacheDecision, CacheReceipt,
   TTL/GC/stats, decision cache, selective invalidation.
5. No Context Gateway contract: no capsule/refs/lazy expand/sufficiency.
6. No EconomyCheckpoint / resume preserving spend.
7. No BudgetReconciliation (planned vs observed per axis, calibration
   error, unresolved when unobserved).
8. No ProviderPricing (declared catalog, effective dates, missing→
   PF-ECONOMY-PRICING-MISSING).
9. No VerificationPlanner (risk floors, security floor, graph-aware
   selection, verification ledger).
10. No EconomyWasteDetector.
11. Agent fanout: no max_agents/max_parallel/max_debate_rounds on an
    envelope; no AgentUniqueness audit.
12. Debate: bounded already; missing RefereePacket, information-gain and
    stagnation stops.
13. Routing: no profiles/scorecard/receipt/decision plane.
14. CLI: `economy report|strategy|compare|qpt|qpt-bench` only — missing
    checkpoint/resume/reconcile/doctor/explain, `context`, `cache`,
    `routing` groups.
15. MCP: no economy surface.
16. Fleet: funnel exists; no fleet query cache, no snapshot-delta.
17. Live: ObservationBudget exists; no CollectionEconomyPlan, provider-
    call ROI, evidence gate formalization.
18. Knowledge: no selector/applicability/pack budget/search tiers.
19. No case-level economy records, cross-run learning, historical
    budget profiles.
20. No usage-import adapters (Codex/Claude/JSONL transcripts).
21. No economy eval categories, property tests, adversarial suite E1–E12,
    doctor eval, benchmark modes.

## Known overlaps

- `economy/engine.py` cost classes ⊂ new routing decision; merge into
  control-plane routing layer rather than parallel picker.
- `tokensave/budget.py check_input_budget` ⊂ BudgetEnvelope (context
  dimension) — keep as the context-dimension checker inside the
  envelope.
- `live/budget.py ObservationBudget` ⊂ envelope provider_calls/
  wall_time dimensions — integrate, don't duplicate.
- `agents/runledger.py` ⊂ unified ledger dimensions (agents/fanout/
  delta_bytes fields already match §129).

## Known dead code

None found in the audited modules — every economy file is wired to a CLI
or test. `EconomyEngine.compare()` shadow rows are recorded but the
projections field is informational only (no consumer yet — becomes the
champion/challenger substrate for §150–152).
