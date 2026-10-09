# Routing Control Plane

`platformforge/routing/decision.py` + `router.py`. ADR-0062.

## Single authority (polish §20–29)

`routing/decision.py::decide(RoutingRequest)` is the **only** producer
of the canonical `RoutingDecision` — it wraps the deterministic router
and applies the effective profile. CLI (`routing explain`) and MCP
(`platformforge_routing_explain`) both call `decide()`; there is no
second adapter.

`EconomyEngine.advice()` returns an `economy-advice/v1` dict
(`advisory: true`) — an *economic recommendation* that may inform a
`RoutingRequest`'s signal but is never a decision. The orchestrator
(`agents/orchestrator.py::prepare`) refuses any `router_decision`
that does not carry `platformforge/routing-decision/v1` — advice,
raw dicts and foreign schemas cannot activate a route.
`EconomyEngine.strategy()` remains as a deprecated alias of
`advice()`.

```text
EconomyEngine.advice()          # advisory — cost class + strategy hint
        ↓ informs signal
RoutingRequest → decide()       # canonical authority
        ↓
RoutingDecision (routing-decision/v1) → orchestrator enforces schema
```

## Profiles

`economy` (deterministic-first, cache, ≤1 specialist),
`balanced` (default), `deep` (expanded context + review),
`strict` (safety over economy, V4 floor),
`offline` (provider_calls hard limit = 0).

`RoutingRequest.effective_profile()`: risk raises the floor
(`critical → strict`); a requested profile can only go *more*
conservative, never less.

## Decision and receipt

`decide(request)` fills `context_budget`/`provider_budget`/
`verification_tier` from `PROFILE_DEFAULTS[effective_profile]` and
stamps `policy_version = platformforge/routing/v2`.

`RoutingDecision(mode, agents, model_tier, context_budget,
tool_budget, provider_budget, verification_tier, reason, risk,
profile, fallback, policy_version)`.
`receipt(request, decision, estimated_budget)` binds inputs hash +
policy version + decision + reason + estimated budget — every routed
run is auditable.

## Champion/challenger

Current route = champion; candidate = challenger in shadow.
`promote_verdict` requires all three gates (quality floor pass,
safety unchanged, economy better) **and** `human_approved=True`.
Verdicts: `rejected` | `awaiting_human` | `promotable`. There is no
auto-promotion and no self-modifying router.

## Scorecard

`RoutingScorecard(run_id, mode, correctness, evidence, tokens, tools,
latency_ms, agents, provider_calls)` — measured per run, feeds reviews.

## CLI / MCP

`routing explain --signal <json>` (receipt for a task),
`routing compare --champion .. --challenger .. [--approved]`,
`routing scorecard ...`. MCP: `platformforge_routing_explain` —
read-only; no `routing.activate` exists.
