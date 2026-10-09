# Economy Parity — Final Matrix

Post-polish statuses (prompt_evo_polish §33, §94). Vocabulary:
`validated` (gates + tests + evals pass on the functional SHA),
`validated-with-limitations` (validated but a declared gap bounds the
claim), `experimental` (exists, not fully validated),
`externally-unverified` (cannot be proven from this repo).

| Capability | Implementation | Status | Boundaries / known gap |
|---|---|---|---|
| EconomyPlan + explainability | `economy/plan.py` | validated | — |
| BudgetEnvelope (11 dims) | `economy/budget.py` | validated | — |
| Unified ledger | `economy/ledger.py` | validated | observed/estimated/never summed |
| Multilayer cache | `economy/cache.py` | validated | analysis layer reuses only under identical rule_catalog+knowledge+engine+policy tuple — conservative by construction |
| Context Gateway | `context/` | validated | essential-evidence refusal preserved |
| Checkpoint/resume | `economy/checkpoint.py` | validated | spend preserved; downgrade refused |
| Reconciliation | `economy/reconcile.py` | validated | unmeasured = unresolved |
| Pricing engine | `economy/pricing.py` | validated-with-limitations | declared-rates engine only; no bundled catalog (by design); missing rate → `unresolved`, never zero |
| Selective verification | `economy/verifyplan.py` | validated | risk floors unlowerrable |
| Agent fanout economy | `agents/uniqueness.py` | validated | — |
| Debate economy | `agents/debate.py` | validated | stagnation stop + RefereePacket |
| Waste detector | `economy/waste.py` | validated | — |
| Routing control plane | `routing/decision.py::decide()` | validated | single authority; EconomyEngine advisory only |
| Fleet economy | `economy/collection.py` | validated | snapshot-keyed; coverage-first |
| QPT/QPC v3 | `economy/qpt.py` | validated | money axis unresolved without declared pricing + observed usage |
| CLI surface | `cli/main.py` | validated | 10 economy verbs + context/cache/routing |
| MCP surface | `mcp/` | validated | read-only; no `routing.activate` |
| Closure receipt | `VALIDATION-RECEIPT.json` | validated | `economy-validation-receipt/v1`, `validated_sha` binds functional HEAD, `closure_sha` null by design |
| Production savings | — | experimental | microbench overhead measured; no production corpus |
| Remote CI | `.github/workflows/ci.yml` | externally-unverified | jobs blocked on GitHub billing (account payments) — external block, not code failure |

Parity claim (§96): same **maturity class** as the strongest Forge
implementations (API Forge, Spark Forge) — not same implementation.
Platform-specific differentiators preserved: fleet-scale context
economy, graph-aware context, provider-call economy, live-observation
budgeting, operations-aware verification, agentic fanout economy.
