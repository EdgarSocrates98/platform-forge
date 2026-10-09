# Economy Control Plane — Architecture

The economy layer is a control plane, not a compressor. It governs
**quality per unit of cost**: context bytes, tokens, tool calls,
provider calls, agent fan-out, wall time and money — while protecting
evidence, security and verification from ever being economized away.

## Pipeline

```text
TASK
 │
 ▼
DETERMINISTIC REACH      EconomyEngine.strategy — cache/parser/index/
 │                       rule/graph first, model last
 ▼
CACHE                    CacheStore — 7 layers, dep-bound invalidation
 │
 ▼
CONTEXT GATEWAY          ContextGateway → ContextCapsule + ContextRef
 │
 ▼
BUDGET ENVELOPE          BudgetEnvelope — 11 dims, soft/hard, protected
 │
 ▼
ROUTING                  profile floor by risk; receipt per decision
 │   ├─ deterministic
 │   ├─ specialist
 │   ├─ coordinated
 │   └─ refuse
 ▼
EXECUTION                agents operate deterministic engines
 │
 ▼
LEDGERS                  TokenLedger (basis-separated) + EconomyLedger
 │                       (tool/provider entries) + unified_view
 ▼
CHECKPOINT               EconomyCheckpoint — spend survives restarts
 │
 ▼
OBSERVED USAGE           transcript-backed observed; else estimated/
 │                       unknown — never silently zero
 ▼
RECONCILIATION           reconcile() — per-axis calibration error
 │
 ▼
QUALITY GATE             QPT floors + VerificationPlanner floor
 │
 ▼
ECONOMY REPORT           unified_view + doctor() + waste findings
```

## Modules

| Module | Contract | Role |
|---|---|---|
| `economy/plan.py` | `EconomyPlan` | canonical plan + six "why" explanations |
| `economy/budget.py` | `BudgetEnvelope`, `Limit` | 11 dims, phase/role narrowing, protected items |
| `economy/cache.py` | `CacheStore`, `CacheDecision` | 7 layers, dep invalidation, TTL, GC, receipts |
| `context/gateway.py` | `ContextGateway`, `ContextRequest` | the only entry point for model/agent context |
| `context/capsule.py` | `ContextCapsule` | bounded redacted payload + `context://sha256/` ref |
| `context/sufficiency.py` | `ContextSufficiencyResult` | sufficient/partial/insufficient measurement |
| `economy/checkpoint.py` | `EconomyCheckpoint`, `CheckpointStore` | spend-preserving resume, no downgrade |
| `economy/ledger.py` | `EconomyLedger`, `TokenAccounting`, `unified_view` | tool/provider/agent entries + one view |
| `economy/reconcile.py` | `reconcile`, `AxisRecon` | planned vs observed per axis |
| `economy/pricing.py` | `ProviderPricing`, `cost` | declared rates or `PF-ECONOMY-PRICING-MISSING` |
| `economy/verifyplan.py` | `VerificationPlanner` | impact-scoped V0–V5 tiers, risk floors |
| `economy/collection.py` | `CollectionEconomyPlan`, `evidence_gate` | live-call gate, ROI, fleet delta/cache |
| `economy/waste.py` | `EconomyWasteDetector` | 10 waste types over ledgers |
| `economy/doctor.py` | `doctor` | health checks; unresolved ≠ healthy |
| `economy/qpt.py` | `quality_per_token`, `quality_per_cost` | measured QPT v2 + v3 multi-axis |
| `routing/decision.py` | `RoutingRequest/Decision/Scorecard` | profiles, receipts, champion/challenger |
| `agents/uniqueness.py` | `AgentUniqueness` | per-run fanout audit |

## Invariants

- Deterministic first: model is the last resort in the strategy order.
- `planned` and `observed` never mix; `unknown` is reported, not zeroed.
- Hard limits never cross silently; exhaustion is `PF-ECONOMY-BUDGET-EXHAUSTED`.
- Essential evidence either fits or the capsule refuses (`PF-CONTEXT-ESSENTIAL`).
- Stale cache/observation never counts as fresh.
- Challengers never auto-promote; routing changes need human review.
- Safety, evidence and verification floors are outside the budget.

## Surfaces

CLI: `economy report/strategy/compare/qpt/qpt-bench/checkpoint/resume/
reconcile/doctor/explain`, `context pack|capsule|inspect|expand|delta|gc`,
`cache stats|inspect|invalidate|gc`, `routing explain|compare|scorecard`.

MCP (read-only): `platformforge_economy`, `platformforge_economy_explain`,
`platformforge_context_inspect`, `platformforge_context_expand`,
`platformforge_routing_explain`. There is deliberately no
`routing.activate` — policy changes stay human.

Validation: `scripts/validate.py --gate economy-*` (12 gates).
