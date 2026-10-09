# Cycle 5.1 — Final Matrix

Maturity levels: `foundation` → `partial` → `implemented` →
`validated` → `lab-validated` → `production-validated`. Nothing below
claims production validation — none exists.

| Capability | Before | After | Implementation | Tests | Evals | Gates | Evidence | Known Gap |
|---|---|---|---|---|---|---|---|---|
| Agent contract | AgentSpec v1 | v2 + TaskSpec/Handoff/Envelope/RunRecord/Debate + JSON schemas | `agents/contracts.py`, `agents/roster.py`, `contracts/` | yes | yes | agents-contract | schema-validated | — |
| Core orchestration | none | planner, spec-review/seal, orchestrator DAG, verifier, critic, referee, guardian | `agents/{taskspec,planner,orchestrator,verifier,critic,guardian,referee}.py` | yes | yes | agents-contract | DAG instantiation against live roster | — |
| Coordinators | none | 5 bounded coordinators | `agents/coordinators.py` | yes | yes | agents-contract | fanout caps | — |
| Specialists | 7 prose-output | 15 finding-contract | `agents/specialists.py` | yes | yes | agents-contract | demote unsupported | — |
| Reviewers | 2 implicit | 6 checklist reviewers | `agents/reviewers.py` | yes | yes | agents-contract | checklist + verdict | — |
| Executors | none | 8 engine wrappers | `agents/executors.py` | yes | yes | agents-contract | deterministic tier | — |
| Router | v1, dangling names | Router V2 + DAG + budgets + reviewers | `routing/router.py`, `rules/catalog/routing.yaml` | yes | yes | agents-routing | `validate_routing()` | — |
| Host mirrors | ungenerated | 205 files × 5 targets + drift gate | `agents/mirrors.py` | yes | host-no-subagents eval | agents-mirrors | generated, never edited | — |
| Agent economy | none | context packs + budget classes + delta + ledger | `agents/contextpack.py`, `economy/`, `agents/runledger.py` | yes | budget-exhaustion eval | agents-economy | charge-before-spend | projections not spends |
| Debate | none | bounded, evidence-cited, receipted | `agents/debate.py` | yes | conflicting-specialists eval | agents-debate | no-evidence refused | — |
| Independence | implicit | mechanical refusal | `agents/verifier.py` | yes | security-review eval | agents-independence | producer≠verifier | — |
| Adversarial | E1–E12 (fleet) | A1–A12 agent probes | `tests/test_agent_adversarial.py` | 13 tests | — | agents-independence | all refused as designed | — |
| Graph scale | O(N·E) diff | SCC condensation + bitset cones, ~154× at 5k | `graph/diff.py`, `graph/query.py` | yes | — | tests + bench | 80 randomized equivalence trials | 100k-node target unmeasured |
| Analytics persistence | schema v1 | v2 + migration chain + vacuum + soak | `analytics/store.py`, `analytics/soak.py` | yes | — | tests + soak | restart/crash/forget verified | single-node only |
| Validation gates | 33 | 40 (+7 agent gates) | `scripts/validate.py`, `.github/workflows/ci.yml` | yes | — | all | receipt JSON | remote CI unverified |
| Evals | 83 | 93 (+10 agent cases) | `evals/cases/agent-*/case.yaml` | — | 93 | evals + agents-evals | deterministic graders | — |
| Agent docs | 0 | 11 docs + 12 ADRs | `docs/agents/`, `docs/adr/0041–0052` | drift gate | — | docs | docs-drift passes | — |

## Definition-of-done mapping

| § | Requirement | Status |
|---|---|---|
| 267 | simple→no agents; domain→specialist; complex→specialist+reviewer; cross→coordinator; conflict→debate; completion→verifier; critical→governance+human gate | met — Router V2 + evals |
| 268 | no route references nonexistent agent | met — `agents-routing` gate |
| 269 | mirrors generated from canonical source | met — 205 files + drift gate |
| 270 | zero-subagent host works via playbook | met — identical evidence/verifier |
| 271 | fanout measured | met — run ledger + bench projection |
| 272 | debate bounded, evidence-based, receipted | met |
| 273 | no self-verification | met — mechanical refusal |
| 274 | no governance bypass | met — PF-OPS-* host boundary |
| 275 | 10k-node benchmark attempted & documented | met — measured 10k/500k-edge |
| 276 | known hotspot measured & improved | met — ~154× at 5k |
| 277 | store survives deterministic replay | met — soak pass |
| 278 | receipt SHA = final HEAD | pending — generated at closure |
| 279 | freeze review READY | met — this doc + FREEZE-REVIEW.md |
