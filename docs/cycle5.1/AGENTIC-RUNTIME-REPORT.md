# Cycle 5.1 — Agentic Runtime Report

## What landed

Cycle 5.1 built the bounded agentic runtime on top of the Cycle 5
deterministic platform: AgentSpec v2 (41 canonical agents), sealed
PlatformTaskSpecs, Router V2, coordinator dispatch, structured
findings, mandatory reviewers, independent verification, bounded
debate, context economy, and run persistence.

## Architecture (as built)

```
DETERMINISTIC CORE
        ▼
EVIDENCE / FACTS / GRAPH / RULES
        ▼
AGENTIC RUNTIME      plan → review/seal → route → DAG → dispatch
        ▼            → findings → reviewers → verifier → verdict
SPECIALISTS / REVIEWERS / COORDINATORS
        ▼
GOVERNED ACTIONS     (host-side; core refuses mutation)
```

## Baseline drift found and fixed

- `routing.yaml` (v1) routed to 6 nonexistent agent names — replaced
  by Router V2 + `agents-routing` gate (`validate_routing()`); a
  dangling name is now a build failure.
- Host mirrors were ungenerated — `agents sync` now renders 205 files
  across `agents/`, `.agents/`, `.claude/`, `.codex/`, `.devin/`;
  `agents check` gates drift.
- Referee expanded to the 10-axis contract (evidence quality,
  coverage, freshness, risk, feasibility, reversibility, blast radius,
  cost, precedent, residual uncertainty).

## Safety properties (machine-enforced)

- Producer can never be sole verifier (`PF-AGENT-INDEPENDENCE`).
- Budget exhaustion → `partial`, never silent success; verification is
  budget-exempt.
- Debate positions without evidence refused at intake; rounds capped
  at 3; referee verdict never replaces verification.
- No mutation verbs in any agent spec; `change approve|apply` stays
  host-side (`PF-OPS-*`).
- Resume preserves spent budget and prior decisions — no reset.

## Validation

93 evals · 44 lab scenarios · 787 unit/integration tests ·
40 validation gates (7 agent-specific) — all green at freeze.

Adversarial suite (A1–A12): fabricated evidence, verifier bypass,
uncontrolled dispatch, critical-review bypass, mirror permission
escalation, budget reset on resume, unbounded debate, direct mutation
by coordinators, self-verification, whole-fleet context overrun,
nonexistent routing references, unnecessary deep route — all refused
or demoted as designed.
