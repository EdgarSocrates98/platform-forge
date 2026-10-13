# RELEASE-HARDENING — freeze sweep (Phase J)

Reproducible release artifacts for `platformforge 0.1.0`, built at the
freeze HEAD. Every artifact is regenerable with `uv build` in a clean
checkout; checksums below pin this build.

## Artifacts

| file | sha256 |
|---|---|
| `dist/platformforge-0.1.0-py3-none-any.whl` (689,514 B) | `b3d0eb3ccf95cdc16afcc8fc4265cc46a4d10bd58abe5efae15a0efe2d6e6aa1` |
| `dist/platformforge-0.1.0.tar.gz` (2,628,666 B) | `b7de44b4ad83a21df77a23b4e0adf5eb897da021fc19846fe6d3856a6454829b` |
| `docs/freeze/SBOM.cdx.json` | CycloneDX 1.x, 42 components (project `.venv`) |
| `docs/freeze/LICENSE-INVENTORY.txt` | all project deps permissive (MIT / Apache-2.0 / BSD / PSF) — no copyleft, no UNKNOWN in shipped deps |

## Dependency health (§release hardening)

- `pip-audit` over the declared dependency set (runtime + dev): **no
  known vulnerabilities** after the pytest 8.4.2 → 9.1.1 bump
  (`PYSEC-2026-1845`, dev-only tool, was the only hit).
- Runtime surface is deliberately small: `PyYAML`, `jsonschema`,
  `python-hcl2`; optional extras `boto3` (live collectors),
  `mcp` (host surface); dev `pytest`, `ruff`.
- All runtime deps carry permissive licenses — see LICENSE-INVENTORY.
- Dependency review cadence: at every release and quarterly alongside
  the knowledge compatibility sweep (LIFECYCLE.md).

## Startup performance

The command-level sweep (CLI parse + first-verb latency for `--help`,
`doctor`, `inspect`, `agents list`, `capability manifest`) is measured
in `PERFORMANCE-RECEIPT.json` — generated on the same host as the scale
benchmarks so the numbers share one environment.

## Reproducibility

```bash
uv sync --extra dev
uv build
sha256sum dist/platformforge-0.1.0-*
```

`uv.lock` pins the full transitive graph; the wheel embeds
`platformforge`, `rules/`, `knowledge/`, and `lab/` data via hatchling
`sources` config.
