# docs/ — design records, agent docs & cycle reports

## Root references

- [CLI-SURFACE.md](CLI-SURFACE.md) — generated exhaustive verb/subcommand/flag index (drift-gated)
- [../CLI-REFERENCE.md](../CLI-REFERENCE.md) — curated guide with examples
- [../CAPABILITIES.md](../CAPABILITIES.md) — capability matrix
- [../AGENTS.md](../AGENTS.md) — working contract for agents in this repo

## agents/ — agentic runtime (Cycle 5.1)

Contracts and matrices for the bounded agent layer (canonical roster:
`platformforge/agents/roster.py`):

- [AGENT_PROTOCOL.md](agents/AGENT_PROTOCOL.md) — TaskSpec/Handoff/Envelope/RunRecord lifecycle
- [AGENT_ARCHITECTURE.md](agents/AGENT_ARCHITECTURE.md) — layered runtime, 41-agent roster
- [AGENT_OUTPUT_CONTRACT.md](agents/AGENT_OUTPUT_CONTRACT.md) — structured findings; demotion rules
- [AGENT_SKILL_MATRIX.md](agents/AGENT_SKILL_MATRIX.md) — domains per agent
- [AGENT_TOOL_MATRIX.md](agents/AGENT_TOOL_MATRIX.md) — verbs/tools/capabilities per agent
- [AGENT_RISK_MATRIX.md](agents/AGENT_RISK_MATRIX.md) — escalation signals, access/model tiers
- [HOST_PARITY.md](agents/HOST_PARITY.md) — generated mirrors, drift gate, zero-subagent playbook
- [ROUTING.md](agents/ROUTING.md) — Router V2 signals, modes, DAG output
- [DEBATE.md](agents/DEBATE.md) — bounded debate + referee contract (10 axes)
- [ECONOMY.md](agents/ECONOMY.md) — context packs, budget classes, run ledger
- [VERIFICATION.md](agents/VERIFICATION.md) — independent verifier, producer ≠ verifier

## adr/ — Architecture Decision Records

Numbered records of load-bearing decisions:

**Foundations (0001–0010)** — deterministic core, Graphfy spine,
economy-by-architecture, provenance classes, redaction boundary, rule
provenance, version semantics, quality-per-token, cloud common model,
golden-path model.

**Observation & graph (0011–0020)** — observation model, collector
boundary, absence semantics, freshness/coverage, temporal Graphfy,
identity resolution, reconciliation classes, runtime edges, credential
boundary, provider-call economy.

**Operations (0021–0030)** — no arbitrary shell, source-of-truth first,
autonomy levels, risk classes, approval hash-binding, operation state
machine, execution adapter boundary, verification ≠ command success,
rollback semantics, policy precedence.

**Fleet & analytics (0031–0040)** — fleet canonical model, org-graph
layers, history boundaries, deterministic baseline first, metric
provenance, optimization→ChangeIntent, federation no-credentials, no
individual scoring, AI-platform boundary, pluggable analytics storage.

**Agentic runtime (0041–0052)** — canonical roster, agents vs engines,
coordinator dispatch boundary, verifier independence, budget model,
context economy, debate/referee contract, host mirror generation,
zero-subagent fallback, operation boundary, fleet-scale context policy,
architecture freeze.

Browse: [adr/](adr/) — filenames carry the title.

## Cycle reports — evidence-backed close-outs

| Cycle | Dir | Highlights |
|---|---|---|
| 2 | [cycle2/](cycle2/) | hardening wave; FINAL-REPORT, matrices, security/economy/quality reports |
| 2.1 | [cycle2.1/](cycle2.1/) | CI validation + receipt |
| 3 | [cycle3/](cycle3/) | live observation boundary; research ledger |
| 4 | [cycle4/](cycle4/) | governed operations; research ledger |
| 4.1 | [cycle4.1/](cycle4.1/) | rollback integrity, expected-delta gates; receipt |
| 5 | [cycle5/](cycle5/) | fleet + analytics + federation; 10 closure docs + receipt |
| 5.1 | [cycle5.1/](cycle5.1/) | agentic runtime: baseline, agent matrix/benchmarks, scale + soak reports, freeze review, final matrix/report, validation receipt |

## freeze/ — architecture freeze (current state)

The repo is under **Architecture Freeze** — no Cycle 6. Maintenance
classes only (bug/perf/security fix, knowledge-update, new-eval,
new-real-world-fixture, compatibility, docs); everything else needs a
FeatureException via [UNFREEZE-RFC.md](freeze/UNFREEZE-RFC.md).

- [README.md](freeze/README.md) — entry point: the rule, lifecycle, artifacts map, corpus commands, case authoring
- [FREEZE-MANIFEST.md](freeze/FREEZE-MANIFEST.md) — frozen surface inventory
- [LIFECYCLE.md](freeze/LIFECYCLE.md) — freeze rules, exception classes, gates
- [FINAL-REPORT.md](freeze/FINAL-REPORT.md) — honest readiness statement (P4 ceiling)
- [FINAL-MATRIX.md](freeze/FINAL-MATRIX.md) — per-dimension P0–P5 evidence matrix
- [ARCHITECTURE-FREEZE-REVIEW.md](freeze/ARCHITECTURE-FREEZE-REVIEW.md) — 14-dimension review
- [DOGFOOD.md](freeze/DOGFOOD.md) — self + cross-Forge dogfooding evidence
- [REAL-WORLD-ISSUES.md](freeze/REAL-WORLD-ISSUES.md) — RW-1…RW-9 ledger (fixes + regressions)
- [SECURITY-REVIEW.md](freeze/SECURITY-REVIEW.md) — threat model + SEC-1 fix
- [KNOWLEDGE-REVIEW.md](freeze/KNOWLEDGE-REVIEW.md) — 59-source freshness sweep
- [RELEASE-HARDENING.md](freeze/RELEASE-HARDENING.md) — wheel/SBOM/license/dep health
- receipts: `AGENTIC-RECEIPT.json`, `PERFORMANCE-RECEIPT.json`,
  `PERFORMANCE-BASELINE.json`, `SOAK-RECEIPT.json`, `VALIDATION-RECEIPT.json`

Evidence corpus (tracked): `.platformforge/cases/` (10 golden + 6
holdout), `.platformforge/ledgers/` (FP/FN records) — replay via
`platformforge cases replay|ledger|ledger-check|route-audit|context-audit`.

## discovery/ — baseline audits

- [forge-audit.md](discovery/forge-audit.md) — sibling-forge audit (§0 baseline)
