# Distribution parity — Platform Forge

Install-2.0 §8.5 parity matrix for `platformforge` (dist `platformforge`,
Hatchling). Three columns: **Checkout** (source tree / `pip install -e .`),
**Wheel local** (wheel built from this branch, installed into a clean venv,
run outside the checkout), **PyPI publicado** (latest released wheel —
`0.1.6`, fetched with `pip download --no-deps platformforge==0.1.6`; it
predates this branch's `forge.json`/`forge.agentic.json` packaging).

Legend: ✅ works · ⚠️ works with documented degradation · ❌ broken ·
— not applicable.

| Surface | Checkout | Wheel local | PyPI publicado (0.1.6) |
|---|---|---|---|
| CLI (`platformforge`, `platformforge-mcp`) | ✅ | ✅ console scripts present in clean venv (runtime deps resolved from the index); `install apply`, `knowledge packs`, `judge`, `install doctor`, `doctor --offline`, `install repair`, `install uninstall` all run from a consumer dir | ✅ same entry points |
| Skills | ✅ | ✅ install renders host skill mirrors (`.claude/skills`, `.agents/skills`); skill assets ride `data/` + portable bundle | ✅ present |
| Agents | ✅ | ✅ roster mirrors land under `.claude/agents`, `.codex/agents`, `.agents/agents` | ✅ present |
| MCP | ✅ | ✅ `.mcp.json` written; `install doctor` `pf:*` integrity checks PASS — `mcp-handshake` BLOCKED without the `mcp` extra (dependency state, not corruption) | ⚠️ entry point exists; not re-verified on published wheel |
| Knowledge | ✅ | ✅ `knowledge packs` enumerates 13 packaged `platformforge/data/knowledge` packs | ✅ `data/knowledge` present |
| Rules | ✅ | ✅ `judge` against empty facts evaluates the packaged catalog (`counts.rules = 63`) | ✅ `data/rules` present |
| Protocols | ✅ | ⚠️ `install apply` writes `AGENT_PROTOCOL.md`; `forge/context/v1` + `forge/context-registry/v1` produced and schema-valid — **but** `_context_manifest` still reads `_REPO_DIR/forge*.json` (= `site-packages/` under wheel), so `integrity.files` digests and agentic-derived fields stay empty until lf-0037's reader wiring lands; `platformforge/data/forge*.json` are now packaged so only the reader remains | ⚠️ same degradation, and the published wheel lacks `data/forge*.json` entirely |
| Evals | ✅ | ✅ `data/evals` packaged (164 entries incl. scenario corpora) | ✅ `data/evals` present |
| Install | ✅ | ✅ `install apply --repo <consumer> --yes` → `forge/InstallReceipt/v1` `status: completed`; `.platformforge/install-receipt.json` + `.mcp.json` + host mirrors + `.forge/context/` written | ⚠️ applies, but capability manifest degraded (Protocols row) |
| Repair | ✅ | ✅ delete `.mcp.json` → `install repair --repo` restores it | ⚠️ same path exists; not re-verified on published wheel |
| Uninstall | ✅ | ✅ `install uninstall --repo` removes managed assets + `.forge/context` capability; `install apply` reinstalls cleanly | ⚠️ same path exists; not re-verified on published wheel |

## Documented degradations under the wheel

- **Context-manifest integrity fields** (lf-0037 wiring gap, tracked):
  `install/service.py::_context_manifest` reads `forge.json`/
  `forge.agentic.json` only via `_REPO_DIR` (`_PKG_DIR.parent` —
  `site-packages/` under `pip install`). This branch ships
  `platformforge/data/forge*.json`; the reader switch to the bundled data
  path (`platformforge/resources.py` already resolves `data/` via
  `importlib.resources` with materialization) belongs to the
  install/service wiring owned by lf-0037 on `cycle/install-context` —
  recorded here per the ownership boundary.
- `install doctor`'s `mcp-handshake` reports **BLOCKED** when the `mcp`
  extra is not installed in the target interpreter — dependency state,
  not install corruption. `pf:workspace`, `pf:receipt`, `pf:manifest`,
  `pf:version_match`, `pf:assets` must be PASS.
- `doctor --offline` is the offline verification path; it must never
  traceback under the wheel (asserted).

## Deliberately not packaged

The sdist ships the full tree (default Hatchling sdist): `forge.json`,
`forge.agentic.json`, `parity.yaml`, `manifest.json`, docs, tests and
scripts all ship there for wheel-from-sdist rebuilds and downstream
verification tooling; the wheel carries only runtime resources.

## Evidence

- Wheel isolation test: `tests/test_wheel_isolation.py`
  (`test_wheel_install_lifecycle_outside_checkout`, marker `slow`) —
  builds the wheel, installs into a clean venv (runtime deps resolved from
  the index; skips honestly when offline), proves `platformforge` imports
  from `site-packages`, then runs install → registry/contract →
  `knowledge packs` → `judge` → `install doctor` → `doctor --offline` →
  repair → uninstall → reinstall from a consumer dir outside the checkout.
  Passing locally.
- `tests/test_artifact_contents.py::TestWheelCarriesDataLayer::
  test_forge_manifests` asserts `data/forge.json` +
  `data/forge.agentic.json` ride every future wheel.
- Wheel contents verified after this branch's packaging fix (675 entries):
  `platformforge/data/{forge.json,forge.agentic.json,rules,knowledge,
  contracts,evals,lab}` + `platformforge/portal_assets` all present.
- Published `platformforge-0.1.6-py3-none-any.whl` (672 entries) inspected:
  every resource group present **except** `data/forge.json` and
  `data/forge.agentic.json` — the gap this branch closes.
- `tests/test_portable_distribution.py` continues to cover the portable
  bundle layer (`build_bundle`/`install_bundle`/`verify_bundle` — offline
  hash-verified installs, `PF-DIST-HASH-MISMATCH`).

## Planned (lf-0037)

`discovery.ops` verbs over `.forge/context/` (`knowledge.search`,
`rules.search`, `capabilities.list`, …) are in flight on
`cycle/install-context`. When merged, extend the wheel test to exercise
them and promote the corresponding cells.
