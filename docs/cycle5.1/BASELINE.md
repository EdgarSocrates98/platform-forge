# Cycle 5.1 — Baseline Audit

Baseline SHA: `48f8120545f02dc82096781b225db5b6f1ec116d`
(`cycle5 polish wave5 — CHANGELOG polish entry + FINAL-REPORT postscript`)

All numbers below were measured on this SHA, not recalled from docs.

## Verified state

| Surface | Command | Result |
|---|---|---|
| Unit tests | `uv run pytest -q` | 669 passed, 0 failed |
| Eval corpus | `platformforge evals run` | 83 pass / 0 fail / 0 unresolved |
| Lab | `platformforge lab run-all` | 44 scenarios pass, 1 profile-guarded skip (`live-kind`) |
| MCP surface | `platformforge mcp tools` | 34 tools registered |
| Scale bench | `platformforge bench scale` | measured at 58/208/808 nodes (≈808 nodes, 3 200 edges) |
| Docs drift | `pytest tests/test_docs_drift.py` | pass |
| Validation gates | `scripts/validate.py` | 33 gates green locally; remote CI unverified |

## Current agentic layer

Canonical roster (`platformforge/agents/roster.py`): **11 agents**

- coordinator: `platform-coordinator`
- specialists: `iac-analyst`, `k8s-analyst`, `gitops-analyst`,
  `sre-analyst`, `finops-analyst`, `security-analyst`, `graph-analyst`
- reviewers: `evidence-reviewer`, `economy-reviewer`
- referee: `consistency-referee` (6 decision axes)

Supporting machinery: `playbook.py` (sequential fallback),
`mirrors.py` (3 host renderers), `referee.py` (evidence-tier
adjudication), `routing/router.py` (signal → mode + agents).

## Gap audit vs Cycle 5.1 target

### G1 — routing references nonexistent agents (confirmed drift)

`rules/catalog/routing.yaml` + `router.py` name agents that are not in
the roster:

```
referenced:  incident-coordinator, security-reviewer,
             architecture-reviewer, change-risk-reviewer,
             finops-coordinator, kubernetes-specialist,
             platform-coordinator
in roster:   platform-coordinator only
missing:     6 of 7 referenced names
```

`router.py` also *synthesizes* names (`f"{domain}-specialist"`,
`f"{domain}-coordinator"`) that exist nowhere. There is no gate
catching this — Cycle 5.1 adds the `agents-routing` gate.

### G2 — host mirrors not materialized

`.claude/agents/`, `.agents/agents/`, `.codex/agents/` do not exist in
the checkout or in git. `platformforge agents sync` generates them on
demand, but nothing enforces freshness and no `agents/` canonical
markdown or `.devin/` mirror exists. Cycle 5.1 generates all hosts +
`agents-mirrors` drift gate.

### G3 — AgentSpec v1 is too thin

Current fields: `name, role, domains, access, verbs, when, never,
inputs, outputs, executors`. Missing per spec §8: `mission`,
`when_not_to_enter`, `required_evidence`, `allowed_tools`,
`allowed_capabilities`, `write_scope`, `model_tier`,
`max_context_budget`, `max_tool_calls`, `max_parallelism`,
`delegates_to`, `cannot_delegate_to`, `reviewers`, `verifier`,
`escalation`, `done_when`. `access` lacks the tiered vocabulary
(`read-only | state-writer | workspace-writer | governed-writer`).

### G4 — no run contracts

No `PlatformTaskSpec` (draft/reviewed/sealed/rejected/expired), no
`AgentHandoff`, no `AgentRunEnvelope`, no `AgentRunRecord`, no `Debate`
model, no `PF-AGENT-*` refusal namespace, no run store.

### G5 — no orchestration core

No planner (intent → TaskSpec), no TaskSpec reviewer/seal, no
orchestration DAG, no independent verifier, no adversarial critic, no
release guardian, no debate engine (only pairwise referee scoring).

### G6 — no agent economy

No per-run ledger (model calls/context bytes/fanout/duration/cache
reuse), no budget classes (tiny/small/standard/deep/critical), no
`AgentContextPack`, no delta-context mechanism.

### G7 — no scale/soak evidence beyond 808 nodes

`graph/bench.py` covers up to ~800 nodes. `graph/diff()` recomputes
`blast_radius` for every shared node — measured `diff_ms` at 808
nodes/3 200 edges ≈ **1434 ms** (vs build ≈ tens of ms). `gaps()`
rebuilds adjacency lists per node. No soak runner exists for the
analytics store.

### G8 — no agent eval/adversarial coverage

Eval corpus has 83 cases, exactly one `routing` case
(`routing-specialist`). No cases for budget exhaustion, verifier
independence, host fallback, debate bounds, or missing-evidence.

## Parity target (per spec §4)

| Capability | API Forge / Spark Forge | Platform Forge @48f8120 |
|---|---|---|
| orchestrator / planner / verifier | explicit | absent |
| adversarial critic / debate referee | explicit | absent / partial (`consistency-referee`) |
| release guardian | explicit | absent |
| domain specialists | explicit | 7 analysts (subset) |
| phase executors | explicit | absent |
| host mirrors | generated | generator exists, mirrors absent |
| routing → real agents | enforced | **drifted (G1)** |

## Non-goals confirmed for this cycle

- No Cycle 6 feature expansion.
- Engines stay deterministic; agents never replace engines.
- No provider/LLM SDK in `platformforge/`; no network in core.
- Agents propose/review/verify; governed ops still execute.
