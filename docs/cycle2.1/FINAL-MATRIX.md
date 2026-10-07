# Cycle 2.1 — Final Matrix

Closure and reproducibility pass over Cycle 2. Every claim below is backed
by a gate in `scripts/validate.py` (the same script CI orchestrates) or a
named test/eval. Receipt: `VALIDATION-RECEIPT.json` (sha-stamped).

| Area | Before | After | Evidence | Tests | Remaining gap |
|---|---|---|---|---|---|
| CI | Billing-blocked (jobs never started); gates hidden in YAML | `scripts/validate.py` is the single gate source; `ci.yml` calls it; `runs-on` resolves via `RUNNER_LABELS` repo var (self-hosted compatible); 13 gates pass locally | `VALIDATION-RECEIPT.json` verdict=validated | `.github/workflows/ci.yml` + local run | Remote green **depends on the account's Actions availability** — verify on the pushed run |
| Python support | 3.11/3.12 assumed | Matrix 3.10–3.13; suite verified green on 3.10, 3.12, 3.13 (`datetime.UTC`, `Self` shims removed) | pytest on each interpreter | 260 tests × matrix | none |
| Rules | Duplicate ids silently merged; garbage `versions:` accepted; missing catalog dir silent | `load_catalog` rejects dup `rule_id`, warns on missing dirs; `Rule.from_dict` validates constraint syntax (fail-loud at load) | `engine.py::_validate_constraint` | catalog tests + evals | none |
| Sources | Rules cited URL strings; `link_rules` did domain-suffix matching | Canonical source ids only; `resolve()` = id or declared `aliases:`; `contract_check` reports duplicate ids + alias collisions | `gate_linkage`, `gate_provenance` | 63/63 linked, `bad_refs` empty | aliases unused today (dead path kept for host registries) |
| Versions | Unknown version → rule still fired `passed`/`violated` | Tri-state: compatible→evaluated; incompatible→`version-mismatch` skip; unknown→`unresolved` finding + refusal metadata; strict→exit≠0 | `evals/cases/k8s-dep-api-*` (incl. skip-reason assertions) | `test_core.py` + 4 version evals | MCP rule-eval path has no `--versions` arg (safe: degrades to unresolved) |
| QPT | Measured payload ≠ delivered payload; measurement after judge; unresolved→violated counted as kept; refuse crashed bench | `retain_content` envelope = exact delivered bytes (truncated bodies + symbols/sources/graph); measure-before-judge; unresolved flip = lost+fp; `refused` verdict; `quality_measurement` honesty label | `QUALITY-PER-TOKEN.md` + bench | `test_qpt_v2.py` (12) | default judge is facts-only — labeled in every receipt |
| Crossplane | `"crossplane.io" not in api` dropped `*.upbound.io` MRs; `notupbound.io` spoofed; junk ProviderConfig classified; empty `atProvider` counted; `spec.resourceRefs` minted XRs | Explicit family tables + dotted suffixes only; ProviderConfig needs group + credentials shape; non-empty `atProvider`; inferred XR needs `compositionRef`/`status.resourceRefs`; v1/v2 conflicts emit `conflict:` signal | `lab/scenarios/crossplane-platform`, 3 eval cases | `test_crossplane.py` (15) | pass-2 XRD table is per-tree (cross-dir XR links need same-tree XRD) |
| Knowledge | No packs | `knowledge/{kubernetes,aws,terraform,crossplane}/` — 13 packs, contract-validated, all consumed by rules/analyzers | `gate_knowledge`, `gate_packs` | `test_knowledge.py` | packs are curated, not exhaustive — gap documented, not hidden |
| Packaging | `rules/`,`knowledge/`,… lived outside `platformforge/` → installed wheel found 0 rules | `resources.data_path()` resolves repo-or-wheel; `force-include` ships all data; gate builds wheel and asserts data inside; every relative-path consumer rewired | `gate_package` (builds + inspects wheel) | wheel smoke: 63 rules + 52 sources resolve in clean venv | clean-env smoke lives in CI yaml (host-level venv ops) |
| Security | `db_password`/`aws_secret_key` evaded kv patterns; `/+=` truncated AWS secrets; PEM multi-line unreachable (per-line scan); store/rtk-expand persisted raw secrets; MCP test vacuous | snake_case prefixes, `/+=` value class, `https`/`ssh`/`ftp` userinfo, whole-file multi-line scan; store writes redacted, expand re-redacts; summary objects redacted; tests prove store+expand carry no secrets | `tests/test_wave_k.py`, `tests/test_redaction.py` | scan/redaction/store tests | marker `sha256[:8]` is a prefix oracle for low-entropy secrets — documented caveat |

## Adversarial review coverage

Three independent reviewers attacked: epistemic correctness, secrets
boundaries, provenance, QPT methodology, packaging, CI reproducibility.
Findings → fixes are in commits `a421c2e` (H1 truth/graph/rules),
`09ec83c` (H2 Crossplane+secrets), `ceff0ea` (H3 QPT/paths/ledger).

## Honest residuals (not blockers, not hidden)

- `quality_measurement: facts-only` — the default QPT judge can't detect
  file-body regressions; custom judges can. Labeled, never claimed.
- `runs-on` resolves via `RUNNER_LABELS` — remote CI green is verified on
  the pushed run, not assumed from local gates.
- `knowledge packs` are a seed corpus (13 packs, 4 domains) — coverage is
  real but thin; expansion is normal-cycle work.
- MCP tools don't accept `--versions` — version-gated rules resolve to
  `unresolved` over MCP (safe direction, capability gap noted).
- Redaction markers (`sha256[:8]`) leak a prefix oracle for low-entropy
  secrets — acceptable for correlation, documented in SECURITY.md.
