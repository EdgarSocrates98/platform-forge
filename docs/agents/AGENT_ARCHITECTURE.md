# Agent Architecture

```
DETERMINISTIC CORE        (engines, facts, rules — offline, no LLM SDK)
        │
EVIDENCE / FACTS / GRAPH / RULES
        │
AGENTIC RUNTIME           (this layer — bounded, auditable)
        │
SPECIALISTS / REVIEWERS / COORDINATORS
        │
GOVERNED ACTIONS          (host-side only; core refuses mutation)
```

Agents are **operators of deterministic engines**, not replacements.
No agent mints evidence, mutates production, or approves its own work.

## Roster (41 agents, canonical in `agents/roster.py`)

| Layer | Agents | Access |
|---|---|---|
| Orchestration | platform-orchestrator, platform-planner, platform-task-spec-reviewer, platform-verifier, platform-adversarial-critic, platform-debate-referee, platform-release-guardian | orchestrator: state-writer; rest read-only |
| Coordinators (5) | incident, change, fleet, optimization, product | state-writer (run state only) |
| Specialists (15) | iac, kubernetes, gitops, sre, finops, security, graph, aws, crossplane, fleet, policy, capacity, product, ai-infra, federation | read-only |
| Reviewers (6) | evidence, operations-safety, security, architecture, privacy, economy | read-only |
| Executors (8) | pf-inventory, pf-extractor, pf-judge, pf-graph-builder, pf-reconciler, pf-simulator, pf-synthesizer, pf-verifier | read-only |

## Dispatch

- `Router V2` (`routing/router.py` + `rules/catalog/routing.yaml`)
  emits a mode + DAG + budgets + mandatory reviewers + verifier.
- Coordinators bound fanout (`max_parallelism`) and collect findings.
- Orchestration loop templates live in `rules/catalog/orchestration.yaml`;
  `build_dag` instantiates stages against the live roster and reports
  missing agents instead of guessing.

## Independence

- Every non-deterministic route includes `platform-verifier`.
- The producer can never be sole verifier (`verify_run` refuses).
- Critical routes add operations-safety and security reviewers.

## Persistence

Runs persist to `.platformforge/runs/` — run_id, task-spec hash, router
decision, agents, handoffs, budget, evidence refs, debates, gates,
verifier, verdict, checkpoint. Resume preserves spent budget and prior
decisions; budget never resets.
