# Comparative Gap Matrix — §5

Comparison by **concept**, not code (§6: adapt, don't copy). Sources:
`api-forge/src/apiforge/{contracts/economy*.py, context/gateway/*,
economy/{pricing,reconciliation,token_ledger}.py, cli_economy.py}`,
`spark-forge-aws/sparkforge_aws/{economy/*, context/*}`.

| Concept | Platform Forge today | API Forge equivalent | Spark Forge equivalent | Missing behavior | Platform applicability | Decision |
|---|---|---|---|---|---|---|
| Economy plan | `engine.strategy()` signal→strategy | `contracts/economy.py` versioned contracts | `context/planner.py` | Canonical `EconomyPlan` w/ full fields + explainability | High — plan is the receipt root | adapt |
| Unified budget envelope | `tokensave/budget.py` (tokens only) + `live/budget.py` (provider only) | budget axes in economy contracts | `context/gateway_budget.py` | One envelope: context/tokens/models/tools/providers/agents/fanout/time/money, hard vs soft | High | adapt |
| Phase/role budgets | budget_class string | per-role budget fields | `agents/budget.py` | Phase budgets (SDD map), protected phases, per-role | High (SDD exists) | adapt |
| Token accounting | `LedgerEntry` basis observed/estimated/unknown + transcript_ref | `economy/token_ledger.py` + `token_economics.py` | `economy/ledger.py` | Already close; needs unified view + tool ledger | High | adapt |
| ONE economy view | none — 3 ledgers | `cli_economy.py` report | `economy/report.py` | Unified report over token+tool+provider+agent | High | adapt |
| Multilayer cache | FTS5 index only | `context/gateway/selection_cache.py` | `economy/cache.py` bounded artifact cache | artifact/fact/graph/finding/context/analysis/decision layers | High — largest gap | adapt |
| Content addressing | file content hash in index | hashed artifacts (ProofReceipt) | content-addressed decision receipts | sha256 content keys everywhere | High | adopt concept |
| Cache dependency graph | none | n/a | decision receipts carry policy version | CacheDependency + selective invalidation | High | adapt |
| Cache receipts | none | ProofReceipt | decision receipts | per-reuse audit receipt | High | adapt |
| Cache GC/stats | none | n/a | bounded cache | stats, gc CLI, TTL only when semantic | Medium | adapt |
| Context Gateway | tokensave packs + AgentContextPack | `context/gateway/` canonical pipeline (levels, refs, dedup, capsule, role_policy) | `context/gateway.py` + profiles (economy/balanced/deep caps) + context_tree + expandable refs | gateway pipeline, `context://` refs, ContextCapsule, lazy expand, sufficiency, role contexts | High | adapt — keep platform scopes (fleet/incident/operation) |
| Checkpoint/resume | none | `contracts/economy_resume.py` | resume verb + freshness resume eval | EconomyCheckpoint, spend persists, no profile downgrade, revalidation on resume | High | adapt |
| Budget reconciliation | none | `economy/reconciliation.py` planned vs observed axes | `economy/reconcile.py` | axes + calibration error + unresolved | High | adopt concept |
| Provider pricing | none — never hardcode | `economy/pricing.py` declared catalog + effective dates | `economy/provider_cost.py` + `facts/pricing.py` | declared pricing file, missing→PF-ECONOMY-PRICING-MISSING | High | adapt |
| Selective verification | none (evals run whole suite) | `verify plan`/`verify escalate` | verification tiers | VerificationPlanner + risk/security floors + ledger | High | adapt |
| Tool output economy | `rtk/compact.py` | `context compact` + detail_level across tools | detail_level 3-tier on 52 tools | compact default + expand-on-demand + receipt | Medium (already partial) | adapt |
| Caveman review | `caveman/compress.py` | agentops workflows | n/a | guarantee: never strip IDs/codes/versions/evidence | Medium | adapt |
| Waste detector | none | n/a | `economy/waste_detector.py` | waste types + findings + recommendation-only | High | adapt |
| Agent fanout economy | runledger measures; router bounds | agentops telemetry | goldset + agent budgets | uniqueness audit, fanout envelope, selective agentics | High | adapt |
| Debate economy | bounded debate + referee | debate rooms | `run-debate` executor + arbitrate | RefereePacket, info-gain stop, stagnation detection | Medium | adapt |
| Routing control plane | Router V2 + routes.yaml + shadow compare | `next-step` routing | `economy/router.py` + `model_router.py` + decision_plane shadow | profiles, scorecard, decision receipt, human-gated promotion | High | adapt |
| Decision plane | none | n/a | `decision_plane.py` + decision_* (validate/shadow/compare/benchmark/receipt) | light decision plane linking cache/context/route/verify/budget receipts | Medium — take the *linking receipt* idea, not the kernel | adapt (§156 do-not-overengineer) |
| QPT | measured QPT + floors + bench | evals economy-hardening/agentic-quality | token_efficient bench + floor checks | QualityPerCost generalized dims | High | adapt — do not regress QPT (§286) |
| Fleet economy | fleetpack funnel | n/a | n/a — **platform advantage** | fleet query cache, snapshot delta | High | keep + extend |
| Live collection economy | ObservationBudget + ProviderCallLedger | evidence gate verb | collect budgets | CollectionEconomyPlan, ROI (facts gained/calls), evidence gate, freshness policy | High — **platform advantage** | adapt |
| Knowledge economy | registry + packs | knowledge select/search | `context/knowledge_pack.py` | PackApplicability, pack budget, freshness, search tiers | Medium | adapt |
| Case-level economy | replay + route/context audit | case records | decision receipts per case | per-case economy record, cross-run budget profile | Medium | adapt |
| Usage import | none (transcript_ref field exists) | host transcript import | `context/host_usage.py` | ProviderUsageAdapter (codex/claude/jsonl) | High | adapt |
| Privacy | redaction boundary | path-outside-root refusals | sanitize on import | ledger redaction, transcript sanitize | High | adapt |
| Economy CLIs | `economy report|strategy|compare|qpt|qpt-bench` | full `cli_economy.py` | decision CLI verbs | grouped: economy/checkpoint/resume/reconcile/doctor/explain + context + cache + routing | High | adapt |
| MCP economy surface | none | MCP tools | n/a | read-only economy.report/explain, context.inspect/expand, routing.explain | Medium | adapt |

## Adopt vs adapt summary

- **adopt (concept verbatim)**: content-addressed receipts everywhere;
  reconciliation axes pattern (planned vs observed with per-axis error).
- **adapt**: everything else — Platform adds fleet scopes, live provider
  calls, governed operations, large graphs the siblings don't have.
- **reject**: Spark Forge's full decision-kernel; embeddings-based search
  (§214 keeps FTS/local-first); copying API Forge's case machinery
  (Platform already has `cases/`).

## Parity definition

Same **maturity class** (§284): every row above reaches "validated"
(measured + tested + receipted) in this repo's own contracts — not the
same internals.
