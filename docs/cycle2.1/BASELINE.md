# Cycle 2.1 — Baseline (pre-closure)

Captured **before** Cycle 2.1 changes, at the tip of `main`. All numbers are
measured locally on this checkout; CI numbers come from `gh run view`.

| Field | Value |
|---|---|
| Commit | `cd3dc6daa473f8647c34f99489e69482325d8e2e` |
| Date | 2025-… (UTC, measured at session start) |
| Python (dev) | 3.12.3 |
| Ruff | 0.16.x (`ruff>=0.7,<1`) |
| `requires-python` | `>=3.10` |

## Local gates (checkout)

| Gate | Result | Command |
|---|---|---|
| pytest | **204 passed** | `pytest -q` |
| Ruff | clean | `ruff check .` |
| Lab | **13/13** | `platformforge lab run-all` |
| Evals | **34/34** (pass 34, fail 0, unresolved 0) | `platformforge evals run` |
| Rule coverage | **63/63** rules named by ≥1 case/scenario | `platformforge evals coverage` |
| MCP tools | **27** | `tool_descriptors()` |
| Agents | **11** | `platformforge agents list` |
| Knowledge sources | **52** registry entries | `SourceRegistry.default()` |

## Interpreter support — verified locally

| Python | Tests |
|---|---|
| 3.10 (uv-managed) | 204 passed |
| 3.11 | (declared by CI matrix, previously passing) |
| 3.12 | 204 passed |
| 3.13 (uv-managed) | 204 passed |

3.10 initially failed (`datetime.UTC`, `typing.Self` — both 3.11+) — fixed in
Phase A. 3.13 passes the full suite → added to the CI matrix.

## CI status (remote, `gh run view`)

| Item | Value |
|---|---|
| Latest runs | `37570303893`, `37569262614` — **failed in ~2–3 s** |
| Failure | `The job was not started because recent account payments have failed or your spending limit needs to be increased.` |
| Root cause | **Account billing/spending limit** — repo is private, jobs never started. Not a code/test/package failure. |
| Mitigation chosen | Self-hosted runner — workflow accepts `vars.PF_RUNNER` (JSON label, default `"ubuntu-latest"`). |

## Known blockers at baseline (from the audit)

1. **Version truth** — `_version_gate` returns `(True, notes)` on unknown
   version → rule still emits `passed`/`violated` with a note instead of
   `unresolved` (`platformforge/rules/engine.py`).
2. **Provenance linkage** — rules reference URL strings; `link_rules` matches
   by domain suffix (`endswith`), not canonical IDs — `k8s.io` could
   wrongly match `gateway-api.sigs.k8s.io`.
3. **QPT methodology** — measured context ≠ evaluator input (facts filtered
   by path subset while the full set was sent as "essential").
4. **Crossplane** — `apiextensions.crossplane.io` handled, but
   `*.upbound.io` and provider-family Managed Resources dropped by the
   `"crossplane.io" not in api` guard.
5. **Knowledge packs** — no machine-readable packs under `knowledge/<domain>/`.
6. **Packaging** — wheel excluded `rules/`, `knowledge/`, `contracts/`,
   `evals/`, `lab/` → installed `platformforge` found 0 rules and crashed on
   `knowledge/sources.yaml` (verified on a clean venv at baseline).
7. **CI matrix** — no 3.10; 3.13 status undocumented.

## Status vocabulary (Cycle 2.1)

`implemented` → code exists · `locally validated` → gates pass on this
checkout · `ci validated` → green on GitHub Actions · `production validated`
→ observed on a real estate. Cycle 2 claims are **locally validated only**;
CI validation is blocked by the billing issue above until a runner is
available.
