# Economy Parity — Final Matrix

Columns: capability · before (pre-cycle) · after · Platform impl ·
Spark Forge equivalent · API Forge equivalent · tests · evals · bench ·
status · known gap.

| Capability | Before | After | Platform impl | SF equiv | AF equiv | Tests | Evals | Bench | Status | Known gap |
|---|---|---|---|---|---|---|---|---|---|---|
| EconomyPlan + explain | none | full | `economy/plan.py` | decision_plane | contracts/economy | contracts | — | — | done | — |
| BudgetEnvelope | per-subsystem ints | 11-dim soft/hard | `economy/budget.py` | — | contracts | contracts | E5/E12 | bench | done | — |
| Unified ledger | tokens only | tokens+tools+provider+agents | `economy/ledger.py` | token_ledger | token_ledger | contracts | eval | — | done | — |
| Multilayer cache | TokenSave reuse only | 7 dep-bound layers | `economy/cache.py` | economy/cache | contracts/cache | cache | E1/E2 | bench | done | analysis layer gated on tests |
| Context Gateway | context packs | capsule+refs+sufficiency | `context/` | context/gateway | context/gateway | gateway | E3/E11 | bench | done | — |
| Checkpoint/resume | none | spend-preserving + no-downgrade | `economy/checkpoint.py` | — | economy_resume | gateway | E4 | — | done | — |
| Reconciliation | none | per-axis calibration | `economy/reconcile.py` | — | reconciliation | gateway | eval | — | done | — |
| Provider pricing | none | declared catalog | `economy/pricing.py` | provider_cost | economy/pricing | pricing | eval | — | done | no real catalog shipped |
| Selective verification | all-or-nothing | V0–V5 impact tiers | `economy/verifyplan.py` | — | — | pricing_verify | E6 | — | done | — |
| Agent uniqueness | none | per-run audit | `agents/uniqueness.py` | — | — | agents_waste | eval | — | done | — |
| Debate economy | bounded | +stagnation +RefereePacket | `agents/debate.py` | — | — | agents_waste | E7 | — | done | — |
| Waste detector | none | 10 types over ledgers | `economy/waste.py` | waste_detector | — | agents_waste | eval | — | done | — |
| Routing control plane | routes.yaml | profiles+receipts+champion/challenger | `routing/decision.py` | decision_plane | — | evals | E10 | bench | done | — |
| Fleet funnel | fleet pack | snapshot-keyed cache+delta+gate | `economy/collection.py` | — | — | fleet_qpt | E9 | — | done | — |
| QPT v3 | tokens only | quality-per-cost all axes | `economy/qpt.py` | token_efficient | token_economics | fleet_qpt | — | bench | done | no model-call corpus yet |
| Doctor | none | 6 checks over ledgers | `economy/doctor.py` | — | — | evals | eval | — | done | — |
| CLI verbs | 5 economy verbs | +checkpoint/resume/reconcile/doctor/explain, cache, context sub, routing | `cli/main.py` | CLI | cli_economy | surface gate | — | — | done | — |
| MCP | economy report only | +explain/context/routing (read-only) | `mcp/` | — | — | — | — | — | done | no routing.activate by design |

All rows done. Known gaps are listed per row — none hidden.
