# docs/ — design records & cycle reports

## adr/ — Architecture Decision Records

Numbered, immutable-ish records of load-bearing decisions:

- [0001](adr/0001-deterministic-core-first.md) — deterministic core-first; LLMs are adapters
- [0002](adr/0002-graphfy-as-spine.md) — Graphfy as the spine
- [0003](adr/0003-economy-by-architecture.md) — economy by architecture
- [0004](adr/0004-planned-provenance.md) — planned edges are never promoted to observed
- [0005](adr/0005-context-redaction.md) — redaction is a pipeline boundary
- [0006](adr/0006-rule-provenance.md) — every rule cites a dated source
- [0007](adr/0007-version-unresolved-semantics.md) — unknown versions → unresolved, not verdicts
- [0008](adr/0008-quality-per-token.md) — economy is measured per task
- [0009](adr/0009-cloud-common-model.md) — one cloud model; providers are dump adapters
- [0010](adr/0010-golden-path-model.md) — golden paths are evidence-checked

## cycle2/ — Cycle-2 close reports

Evidence-backed final reports for the Cycle-2 hardening spec
(`prompt_evo_cycle2.md`):

- [FINAL-REPORT.md](cycle2/FINAL-REPORT.md) — wave-by-wave delivery + verified numbers
- [FINAL-MATRIX.md](cycle2/FINAL-MATRIX.md) — capability truth matrix
- [FINAL-ECONOMY.md](cycle2/FINAL-ECONOMY.md) — measured perf/token baselines
- [FINAL-QUALITY.md](cycle2/FINAL-QUALITY.md) — test/coverage/precision gates
- [FINAL-SECURITY.md](cycle2/FINAL-SECURITY.md) — redaction & boundary report
- [ARCHITECTURAL-REVIEW.md](cycle2/ARCHITECTURAL-REVIEW.md) — honest architecture assessment
- [NORTH-STAR.md](cycle2/NORTH-STAR.md) — the invariants the platform keeps

## discovery/ — baseline audits

- [forge-audit.md](discovery/forge-audit.md) — sibling-forge audit (§0 baseline)
