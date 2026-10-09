# docs/freeze/ — Architecture Freeze

The repository is under an **architecture freeze**: the surface is
complete enough; the job now is evidence, stability and honest
readiness — not more features. No Cycle 6.

## The rule

> Agents operate deterministic engines; freeze exists so we can prove
> the engines work before adding more of them.

Allowed without ceremony: `bug-fix` · `performance-fix` ·
`security-fix` · `knowledge-update` · `new-eval` ·
`new-real-world-fixture` · `compatibility-update` · `documentation`.
Everything else needs a `FeatureException`
(`docs/freeze/exceptions/<id>.json`, validated by
`platformforge freeze exception --spec <file>`); approval requires a
named `real_world_blocker` — "because it's cool" is a non-reason.

## Lifecycle

`LIFECYCLE.md` is the contract: manifest → snapshot → gate → exception
→ unfreeze RFC. `UNFREEZE-RFC.md` is the RFC template;
`docs/freeze/rfc/` holds submitted ones.

## Artifacts map

| File | What it is |
|---|---|
| `FREEZE-MANIFEST.md` | frozen surface inventory — **generated** from live registries, never hand-maintained |
| `snapshots/` | contract snapshots (schemas/CLI/MCP/capabilities/agents); `freeze check` reports breaking drift |
| `FINAL-REPORT.md` | honest readiness statement — P4 ceiling, no P5 claim |
| `FINAL-MATRIX.md` | per-dimension P0–P5 evidence matrix |
| `ARCHITECTURE-FREEZE-REVIEW.md` | 14-dimension review (READY / READY WITH LIMITATIONS) |
| `DOGFOOD.md` + `dogfood/` | self + cross-Forge dogfooding evidence |
| `REAL-WORLD-ISSUES.md` | RW-1…RW-9 ledger: every real-world defect found, its fix commit and regression pointer |
| `SECURITY-REVIEW.md` | threat model + SEC-1 containment fix |
| `KNOWLEDGE-REVIEW.md` | 59-source freshness sweep |
| `RELEASE-HARDENING.md` | wheel/sdist hashes, CycloneDX SBOM, license inventory, dep audit |
| `exceptions/FE-001.json` | deferred FeatureException — fixture-aware scoping (RW-4/RW-7) |
| `*-RECEIPT.json` | machine receipts bound to the measured commit: `PERFORMANCE`, `PERFORMANCE-BASELINE`, `SOAK`, `AGENTIC`, `VALIDATION` |

## Evidence corpus (tracked in git)

```
.platformforge/cases/<golden|holdout>/<id>/case.yaml   # the corpus
.platformforge/ledgers/{false-positives,false-negatives}.yaml
```

```bash
platformforge cases validate          # case.yaml contract check
platformforge cases replay            # deterministic replay, canonical hash
platformforge cases ledger-check      # every record's regression pointer resolves
platformforge cases route-audit       # Router V2 over the corpus
platformforge cases context-audit --stamp   # measured context_cost
platformforge freeze check            # contract drift + exceptions gate
```

Gates in `scripts/validate.py`: `freeze-contracts`, `freeze-docs`,
`freeze-replay`, `freeze-exceptions`.

## Authoring a new case (new-eval / new-real-world-fixture)

`platformforge cases template --out dir/case.yaml` — required fields:
`id`, `classification` (synthetic | fixture-derived | real-anonymized |
real-live | production), `tier` (golden | holdout), `task`, `scope`,
`expected_known_truth` (`violated_rules` / `absent_rules` /
`fact_kinds`). Fixture via `fixture_from: <dir>` (resolved to
`<dir>/fixture`) or a case-local `fixture/`. Holdout cases are never
tuned against — add only after the fix is proven elsewhere.

FP/FN verdicts on real findings become ledger records
(`.platformforge/ledgers/`) with a `regression_test` pointer that must
resolve — the gate enforces it.
