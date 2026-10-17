# PyPI patch plan — platformforge

Cycle 11.2 (P1-004 + P1-006). Prepared for maintainer approval; nothing here
publishes, tags or uploads anything.

## Current state (audited in cycle 11.2)

| Signal | Value |
|---|---|
| PyPI published | `platformforge 0.1.0` (only release) |
| `pyproject.toml` | `0.1.0` — aligned |
| Git tag / GitHub release | `v0.1.0` — aligned |
| `requires-python` | `>=3.10` |
| CI matrix | `["3.10","3.11","3.12","3.13"]` — complete per cycle-11.2 audit; no gap |
| Classifiers before this PR | 3.10 / 3.11 / 3.12 — **missing 3.13 although CI tests it** |

**No version drift**: PyPI = pyproject = tag = GitHub release.

## What changes in this PR

1. **Classifiers**: added `Programming Language :: Python :: 3.13` — the CI
   matrix already covers it, so the published metadata lagged reality.
2. `project.urls`, `license`, `description`, `readme` already coherent and
   all URL targets exist (`CHANGELOG.md`, `docs/README.md`).

Not changed: the CI matrix (audit found no gap) and `requires-python`.
Python **3.14** is inside `>=3.10` but currently untested in CI — adding it
is a candidate for the next cycle once a leg is proven.

## Proposed next release: `0.1.1` (patch)

Rationale: classifier correction only; no code/dependency change.

### Provenance checklist for the maintainer

- [ ] `uv run pytest -q && uv run ruff check .` (repo gate).
- [ ] `python scripts/validate.py --gate package` green.
- [ ] Bump `version = "0.1.1"` in `pyproject.toml` at release time.
- [ ] Tag `v0.1.1` after merge; publish via `publish-pypi.yml`.
- [ ] Verify the PyPI page lists 3.10–3.13 classifiers.

## Local smoke evidence (this PR)

- Interpreters: system `python3.12` (3.12.3); uv-managed 3.10.21, 3.11.16,
  3.13.15, 3.14.7.
- `uv pip install -e ".[dev]"` on 3.12: clean; `platformforge --help` and
  `platformforge doctor` smoke OK.
- `python -m build --wheel` builds the wheel.

## Blockers

None.
