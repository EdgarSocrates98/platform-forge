# CI-VALIDATION — Cycle 2.1 §12 receipt

Status: **blocked — no CI provider configured** (honest, per §12:
"Não dizer 'CI green' baseado apenas em execução local").

## Required receipt fields

| Field | Value |
|---|---|
| latest main SHA | `n/a` — no CI run exists to record |
| GitHub Actions run ID | `n/a` — no `.github/workflows/` in this repo |
| all jobs | `n/a` |
| conclusion | `n/a` |

## What exists instead (local gate equivalence)

`scripts/validate.py` is the single validation source a CI pipeline
must orchestrate (it must not re-implement gates). Current gate map vs.
the §11 required list:

| §11 required | validate.py gate | locally |
|---|---|---|
| ruff | `lint` | PASS |
| pytest | `tests` | PASS |
| package build | `package` | PASS |
| clean wheel install | `package` (force-include check) | PASS |
| rule provenance | `provenance` | PASS |
| knowledge contracts | `knowledge` | PASS |
| rule-source exact linkage | `linkage` | PASS |
| evals | `evals` | PASS |
| eval coverage | `coverage` | PASS |
| lab L0 | `lab` | PASS |
| MCP/CLI parity | `mcp-parity` | PASS |
| docs drift | `docs` | PASS |
| secret/redaction tests | `security` | PASS |
| offline tests | `security` | PASS |
| (added in gap closure) dogfooding | `self` | PASS |

Latest local receipt: `docs/cycle2.1/VALIDATION-RECEIPT.json`
(cycle 2.1) plus `python scripts/validate.py --receipt <out>` for the
current tree.

## Unlock

Provision a CI workflow (e.g. `.github/workflows/ci.yml`) whose only
job step is `python scripts/validate.py --receipt ci-receipt.json`,
then record SHA / run ID / jobs / conclusion here and flip the status
to `validated`. Until then every "green" claim in this repository is
**locally validated only**.
