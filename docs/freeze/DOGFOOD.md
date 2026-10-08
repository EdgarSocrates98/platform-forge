# DOGFOOD receipts — Phase H (§43–§51)

Read-only dogfooding of Platform Forge against itself and the two
sibling forges. Artifacts in `dogfood/`; issues in
`../REAL-WORLD-ISSUES.md`.

## SELF — platform-forge @ freeze

Commands: `inspect`, `collect --detail-level full`, `graph build`,
`graph stats`, `graph gaps`, `judge`, `analyze k8s|iac|secrets`.

| surface | result |
|---|---|
| inspect | argocd 234, backstage 1, crossplane 234, gha 3, k8s 237, terraform 5 |
| collect | 17 detected files, 69 facts, 51 undetected (after RW-1 fix) |
| graph | 38 nodes / 14 edges, `graph_hash 728f7eaf…`; kinds incl. iam_principal, argocd_application, terraform_module, bucket |
| graph gaps | `unreachable: [workload/prod/api]` surfaced (fixture-derived node) |
| judge | 63 rules, 40 violated — dominated by lab/evals fixtures (RW-4) |
| analyze k8s/iac/secrets | ran clean; findings live in fixtures |

**§44–§50 answers.** All 40 violated rules trace to lab/evals fixtures —
our own real workflows are clean. Ownership gaps: `catalog-info.yaml`
has `has_owner: false` in the no-owner fixture — expected. Real
finding: `collect` and `judge` each crashed on honest input before this
phase (RW-1/2/3) — the pipeline `collect → judge` had never been run
end-to-end on a real repo. That is exactly the gap dogfooding exists to
close.

## CROSS — api-forge (read-only, boundary respected)

`inspect` counted argocd 550, crossplane 550, k8s 554, terraform 3 —
`collect` detected 7 files / 33 facts / **4159 undetected**; `judge`:
30 violated, dominated by `PF-SEC-010` noise that led to RW-5 fixes.
Remaining hits post-fix: `password_kv` on agent markdown mirrors
(3 copies of one doc — same line, three hosts) and `conn_string` in a
test fixture; `PF-CICD-004` on a workflow (true positive — informational).

## CROSS — spark-forge-aws (read-only)

`inspect` counted argocd 785, crossplane 785, k8s 790, terraform 74 —
`collect` detected 8 files / 21 facts / **5688 undetected**; `judge`:
18 violated, `PF-SEC-010` on `fixtures/**` (literal fixture secrets —
RW-7 accepted) and `PF-IAC-003` on a terraform fixture.

## Coverage honesty (RW-6)

Both sibling forges are code-dominant repos. Detection coverage is thin
**by design** — Platform Forge reads platform artifacts (manifests,
policies, plans, dumps), not source trees. `undetected` is always
reported, never silently dropped. The numbers above are the honest
coverage bound and are carried into FINAL-REPORT.

## What dogfooding changed in the code

- `collect/detect.py` — bool-key guard, `.pytest-tmp`/`pytest_cache` ignored
- `cli/main.py cmd_judge` — malformed fact entries skipped + reported
- `cicd/{backstage,dockerfile,gitlab_ci}.py` — `PF-*` fact_id contract
- `security/scan.py` — tool/binary skips + `truncated` flag
- `core/redaction.py` — `password_kv` prose guard
- `tests/test_surface.py` — 5 new regression tests

All regression tests green; replay corpus 15/15; suite 851 tests pass.
