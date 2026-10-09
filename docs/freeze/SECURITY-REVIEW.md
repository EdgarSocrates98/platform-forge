# SECURITY-REVIEW — freeze sweep (Phase I)

Scope: the offline core (`platformforge/`), the sandbox boundary, secret
handling, path handling, and adversarial input posture. This review is
evidence-bound: every claim cites a test, a rule, or a measured run.

## Boundaries (contract, unchanged by freeze)

- Offline core: no provider SDK, no LLM SDK, no network inside
  `platformforge/` — enforced by the import-lint gate
  (`tests/test_architecture*.py` family) and exercised by
  `tests/test_live_security_props.py`.
- Agents never mutate production; `change approve|apply` are host-side
  refusals with `PF-*` codes.
- Redaction is a boundary pipeline; secret values are never emitted —
  `test_secret_scan_never_emits_values`, `test_receipt_never_carries_values`,
  `test_index_redacts_before_fts`, `test_secret_in_envelope_serialization`.
- Live collectors refuse mutation verbs and credential flags —
  `test_k8s_transport_refuses_mutating_verbs`,
  `test_k8s_transport_refuses_credential_flags`,
  `test_aws_transport_refuses_write_ops`.

## Findings fixed during this review

| id | severity | issue | fix |
|----|----------|-------|-----|
| SEC-1 | F1 | `Sandbox.write_file` joined `dst / rel` without containment — a `../` rel path could write outside the sandbox copy | resolve + root-containment check raising `ValueError`; `sandbox_analyze` converts it to `platform.sandbox.path_escape` refusal (PF- alias automatic); `test_sandbox_write_file_refuses_escape` |
| SEC-2 | F2 | `scan_secrets` walked tool/test caches (`.pytest-tmp`, `.tokensave`, `.rtk`) and scanned binary formats as text (`.db`, `.exe`) — pure noise plus wasted IO; `max_files` truncation was silent | `_SKIP_DIRS`/`_SKIP_EXT` extended; `truncated` reported; regression tests added |
| SEC-3 | F2 | `password_kv` redaction pattern matched ordinary prose (`pass: refuse`) — same class as the §88 false-positive guard it sits beside | value must now contain ≥1 non-lowercase character; `test_password_kv_prose_not_secret` |

## Adversarial re-runs (§security sweep)

`collect` over a corpus of binary garbage, truncated YAML, unclosed
flow mappings, non-dict JSON, and a 200k-line YAML: exit 0, 0 facts, all
undetected files reported — no crash, no partial facts.

Dogfooding (Phase H) also surfaced two input-robustness crashes fixed
in-place: YAML boolean keys (`on:` → `True`) in `detect_file`, and
detail-projection `_truncated` sentinels reaching `judge`. Both have
regression tests.

## Injection posture

- No shell strings reach a shell: all `subprocess.run` calls use argv
  lists (`forge/manifest.py`, `forge/collect.py`, `ops/executors/base.py`,
  `sandbox/env.py`, `k8s/helm.py`, `graph/bench.py`); `shell=True`
  appears nowhere in `platformforge/`.
- `ops/executors/base.py` documents the argv-only contract; executor
  commands are allowlisted action names, not free text.
- No `eval`/`exec` of artifact content; YAML uses `safe_load`/
  `safe_load_all`.

## Path handling inventory

| surface | posture |
|---|---|
| `Sandbox.write_file` | contained (SEC-1 fix) |
| `Sandbox.apply_patch` | external `patch -p1 -d dst` inside `mkdtemp`; GNU patch itself refuses `..` paths; sandbox destroyed on exit |
| `Workspace.member_paths` | `root / member.path` resolved — members are operator-declared in `workspace.yaml`, not untrusted input |
| `collect`/`analyze` walks | `_IGNORE` set excludes VCS/tool dirs; read-only, never writes |
| `scan_secrets` | skip-sets extended; `max_files` cap now reports `truncated` |

## Known residual risks (accepted, documented)

- `apply_patch` inherits the system `patch` binary's parsing — a missing
  binary fails closed (`applied: false`).
- Secret scanning is heuristic: fixture directories containing literal
  secret-shaped values still report (RW-7) — detection stays honest;
  scoping is RW-4's feature-exception work.
- `password_kv` tightening trades a small FN risk (all-lowercase real
  passwords) for prose-precision — recorded in the FP/FN ledger.

## Verdict

No F0 and no open F1 remain after SEC-1..3 + RW-1..5 fixes. Boundary
properties hold under their existing tests; the freeze adds the missing
containment check the sandbox contract assumed.
