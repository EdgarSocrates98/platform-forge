# Research Ledger — Cycle 5 polish

External standard checks performed against live sources (2026-10-08).
Each entry states what was found, what the project does with it, and
what was deliberately NOT claimed.

## FinOps FOCUS

- **Found**: FOCUS 1.4 ratified 2026-06-04 — adds Billing Period and
  Contract Commitment datasets, 47 columns, correction handling.
  Validator conformance coverage: 1.3 (1.4 validator later in Q3 2026).
- **Project impact**: `finops/focus.py` validated against a free-form
  `spec_version` — any string (e.g. `"99.9"`) could yield a
  `focus_compliant` verdict. Pinned to `FOCUS_KNOWN_VERSIONS`
  (1.0–1.4); unknown versions now refuse
  (`PF-FINOPS-FOCUS-VERSION`). Added `detect_datasets()` — best-effort
  signature detection for cost-and-usage / billing-period /
  contract-commitment; reported as *detected*, never *conformant*.
- **Not claimed**: full 1.3/1.4 dataset conformance — we check the
  Cost and Usage column contract only; `scope` field says so.

## CycloneDX

- **Found**: v1.7 released 2025-10-21 (ECMA-424 2nd ed, Dec 2025) —
  adds CBOM cryptographic transparency, TLP distribution constraints,
  patent info, citations, license-expression details.
- **Project impact**: `security/supply.py` SBOM checks are
  version-agnostic (component/digest/license presence), so no code
  change required. CBOM fields are not consumed — noted as a gap.
- **Not claimed**: CycloneDX 1.7 conformance or CBOM analysis.

## SLSA

- **Found**: SLSA v1.0 is the stable spec; requirements split
  Producer vs Build platform (provenance Exists/Authentic/Unforgeable,
  hosted→isolated isolation). Provenance verification guidance is
  explicit: builder identity map, signature verify,
  `buildType`/`externalParameters` match.
- **Project impact**: `security/supply.py` already models the
  in-toto/SLSA attestation shape (statement + predicate +
  digest-bound subjects) and requires digest binding before any
  trust claim — consistent with the verification guidance.
- **Not claimed**: SLSA level attestation — we verify attestation
  *shape and binding*, not builder trust or level.

## Method note

All findings from public spec pages (focus.finops.org, cyclonedx.org,
slsa.dev). No claim in the repo was upgraded on research alone —
changes are pinned-version honesty plus detection-only additions.
