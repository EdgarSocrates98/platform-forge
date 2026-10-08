# Cycle 5.1 — Agent Matrix

Canonical roster: `platformforge/agents/roster.py` — 41 agents,
all linted by the `agents-contract` gate and mirrored to five host
surfaces (`agents-mirrors` gate).

## Orchestration core (7)

| Agent | Role | Access | Model tier | Parallelism |
|---|---|---|---|---|
| platform-orchestrator | orchestrator | state-writer | standard | 4 |
| platform-planner | planner | read-only | standard | 1 |
| platform-task-spec-reviewer | reviewer | read-only | fast | 1 |
| platform-verifier | verifier | read-only | critical-review | 1 |
| platform-adversarial-critic | critic | read-only | critical-review | 1 |
| platform-debate-referee | referee | read-only | critical-review | 1 |
| platform-release-guardian | guardian | read-only | deterministic | 1 |

## Coordinators (5)

| Agent | Domains | Max fanout |
|---|---|---|
| platform-incident-coordinator | incident, runtime, sre | 4 |
| platform-change-coordinator | change, ops | 3 |
| platform-fleet-coordinator | fleet | 6 |
| platform-optimization-coordinator | capacity, finops, optimization | 6 |
| platform-product-coordinator | dx, golden-paths, product | 3 |

## Specialists (15)

iac · kubernetes · gitops · sre · finops · security · graph · aws ·
crossplane · fleet · policy · capacity · product · ai-infra ·
federation — all read-only, `standard` tier, parallelism 1.

## Reviewers (6)

| Agent | Checklist domain | Tier |
|---|---|---|
| platform-evidence-reviewer | evidence | critical-review |
| platform-operations-safety-reviewer | change, ops | critical-review |
| platform-security-reviewer | security | critical-review |
| platform-architecture-reviewer | architecture | critical-review |
| platform-privacy-reviewer | privacy | critical-review |
| platform-economy-reviewer | economy | standard |

## Executors (8)

pf-inventory · pf-extractor · pf-judge · pf-graph-builder ·
pf-reconciler · pf-simulator · pf-synthesizer · pf-verifier — all
read-only, deterministic/fast tier, `max_tool_calls` 4–16, may not
delegate.

## Contract invariants (enforced)

- Every agent declares `when_to_enter`, `when_not_to_enter`, `never`.
- Only orchestrator/coordinator roles hold non-read-only access.
- Executors never delegate; coordinators have closed `delegates_to`.
- `verifier == name` is a contract error — self-verification refused.
- 205 mirror files generated across 5 targets; drift = gate failure.
