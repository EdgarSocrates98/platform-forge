# REAL-WORLD-ISSUES ledger

Status: **active** — populated by Phase H dogfooding (self + cross-Forge)
and the replay corpus (Phase C/D).

Severity scale: **F0** data corruption / unsafe mutation / secret leak;
**F1** wrong verdict presented as fact, missing `unresolved`, crash on
valid input; **F2** degraded usefulness (over-routing, wasted context,
noisy detections); **F3** cosmetic / DX.

Convention (Phase D): every entry maps to a fix commit and a regression
test or eval case. An issue is `fixed` only when its regression is green.

| id | severity | source | symptom | status | fix / regression |
|----|----------|--------|---------|--------|------------------|
| RW-1 | F1 | self `collect` | `detect_file` crashed on YAML boolean keys (`on:` parses as `True`; `k.startswith` on a bool) | fixed | `detect.py` guards `isinstance(k, str)`; `tests/test_surface.py::test_collect_yaml_boolean_keys_no_crash` |
| RW-2 | F1 | self `judge` | three analyzers emitted non-`PF-*` fact_ids (`backstage-*`, `dockerfile-*`, `gitlab-ci-*`); `judge` crashed validating them | fixed | prefixes corrected to `PF-BACKSTAGE`, `PF-DOCKERFILE`, `PF-GITLABCI`; covered by `test_judge_skips_projection_sentinels` + full-suite replay |
| RW-3 | F1 | self `judge` | a `normal`/`summary` detail-level projection appends `{"_truncated": n}` inside `facts`; feeding it to `judge` crashed `Fact.from_dict` | fixed | `cmd_judge` skips malformed entries and reports `counts.skipped_inputs` + `skipped_facts`; `test_judge_skips_projection_sentinels` |
| RW-4 | F2 | self `judge` | 40 violations on own repo are dominated by intentionally-bad lab/evals fixtures — detection is correct but reads as repo posture | open (known gap) | needs a scoping mechanism (fixture-aware tiers or `--exclude`); feature-class change → FeatureException FE-001 required post-freeze |
| RW-5 | F2 | api-forge `secrets` | `password_kv` pattern matched prose (`generation pass: refuse…`), `scan_secrets` walked `.pytest-tmp` generated keys and tool binaries (`.rtk/rtk.exe`, `.tokensave/tokensave.db`), and `max_files` truncation was silent | fixed | pattern requires ≥1 non-lowercase non-space char in the value; `_SKIP_DIRS`/`_SKIP_EXT` extended; output now reports `truncated`; `test_scan_secrets_skips_tool_dirs`, `test_password_kv_prose_not_secret` |
| RW-6 | F2 | api-forge / spark-forge-aws `collect` | on code-dominant repos, detection covers a handful of files (api: 7 detected / 4159 undetected; spark: 8 / 5688) | by design | PF analyzes platform artifacts, not source — `undetected` is reported, never silent. Recorded as an honest coverage bound in FINAL-REPORT; not a defect |
| RW-7 | F3 | spark-forge-aws `secrets` | remaining `PF-SEC-010` hits are on `fixtures/**` test inputs containing literal secret-shaped values | open (accepted) | fixtures genuinely contain secret patterns — the finding is technically true; distinguishing "fixture secret" from "repo secret" is the same scoping gap as RW-4 |
| RW-8 | F1 | repo `.gitignore` (post-freeze audit) | `.platformforge/` ignored the **entire** evidence corpus — 15 case.yaml + both ledgers existed only in the working tree; a fresh clone would run `freeze-replay`/`ledger-check` on zero cases and receipts referencing an uncommitted corpus | fixed | `.gitignore` un-ignores the root dir and re-includes `cases/` + `ledgers/` only (`.platformforge/*` still ignores index.db, store, receipts, nested litter); all 18 corpus/ledger files now tracked; verifier: `git ls-files .platformforge` non-empty + `cases replay` green on clone |
| RW-9 | F2 | perf bench (post-freeze audit) | `graph diff` ran `gaps()` twice — full sweeps + Tarjan articulation — even when graphs were identical; no-op 50k-node diff dominated by wasted sweeps | fixed | hash-equality fast path (hashes are output fields anyway) + structural shortcut skip both sweeps and the semantic pass; `test_diff_identical_structure_skips_gap_sweeps` |

## Replay-corpus FP ledger (Phase D, deterministic)

`platformforge cases replay` records `false_positives` per case —
currently informational (verdict stays `pass`; they denote violated
rules beyond the case's expected set):

| case | tier | rules flagged beyond expectation |
|------|------|-----------------------------------|
| k8s-bad-readiness | golden | PF-K8S-025 |
| k8s-single-replica | golden | PF-K8S-008 |
| network-policy-missing | golden | PF-K8S-008, PF-K8S-025 |
| demo-platform | holdout | PF-K8S-003/005/007/008/012/025 |
| k8s-missing-limits | holdout | PF-K8S-025 |

These are broad-spectrum k8s rules firing on multi-issue fixtures —
recorded for review in the final freeze matrix, not judged false by
fiat. A rule is only a confirmed FP after human review marks the
fixture truth `expected-violated: false` for it.
