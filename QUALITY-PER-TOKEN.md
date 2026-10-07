# QUALITY-PER-TOKEN — measured economy, not asserted savings

§30–32 + cycle 2.1 §34–50, ADR-0008. Economy claims are evidence-bound: we
measure what a context pack preserves per byte spent, on the same task, and
report both sides.

## The methodology (cycle 2.1)

`economy qpt --path <facts.json> --task <t>` builds two `ContextEnvelope`s —
`full` (every indexed file body + all facts + findings) and `tokensave`
(the pack's actual payload: selected file bodies + essential facts) —
serializes both with the *same* canonical serializer, estimates tokens on
exactly those bytes, and hands each envelope to the *same* judge (rule
engine over `env.facts`, `--versions`-aware).

**Measured == evaluated, by construction.** The pre-2.1 path measured a
facts subset filtered by path while the pack silently carried all facts —
the two were not the same context. That is the methodological bug cycle 2.1
fixed.

## Deterministic vs model context (§38)

Facts the local engine reads are a *deterministic working set*, not model
spend — they land in ledger fields `deterministic_input_bytes` /
`deterministic_fact_count`, and never in `model_context_*`. Provider token
counts stay `unknown` (None) unless a host transcript supplies them; local
counts are always labeled `estimated_tokens`.

Ledger fields (§42): `deterministic_input_bytes`,
`deterministic_fact_count`, `model_context_bytes`, `model_context_tokens`,
`model_output_tokens`, `cache_tokens` — plus the pre-existing
observed/estimated split and `token_basis`.

## The receipt

```json
{"baseline":  {"model_context_bytes": 0, "estimated_tokens": 0,
               "findings_violated": [], "findings_unresolved": [],
               "judge_seconds": 0.0},
 "optimized": {"model_context_bytes": 0, "estimated_tokens": 0,
               "pack_refusals": []},
 "quality":   {"finding_recall": 1.0, "finding_precision": 1.0,
               "evidence_recall": 1.0, "evidence_precision": 1.0,
               "false_negatives": 0, "false_positives": 0,
               "unresolved_recall": 1.0, "unresolved_lost": [],
               "floors": {}, "floors_ok": {}},
 "economy":   {"token_reduction": 0.0, "byte_reduction": 0.0},
 "verdict":   "beneficial | no_reduction | optimization_not_beneficial"}
```

Verdicts are honest: `optimization_not_beneficial` when byte/token savings
exist but a quality floor fails (quality wins over economy — always);
`no_reduction` when the pack didn't actually shrink the payload (on small
fixtures pack overhead can exceed the drop — the receipt says so).

## Corpus (§43–46)

`economy qpt-bench` runs the fixed task corpus under `evals/qpt-bench/` —
Terraform security review, Kubernetes review, GitHub Actions security
review, IAM investigation, incident evidence analysis, change review —
each analyzed → facts → indexed → full vs packed → same judge, same rules,
same versions. Under `--strict` a non-beneficial verdict exits 2.

## Benchmarks (§148–149)

`bench run` measures index time / rule execution / graph build / context
build on the eval fixtures. `bench tokens` measures caveman compression
on small/medium/large subsets. Results are baselines labeled
`measured, not a claim` — never "70% fewer tokens" without a baseline
(§147).

## The rule

- A ratio is only meaningful next to what was lost.
- `payload_bytes` is measured; provider tokens are `unresolved` unless a
  host transcript supplies them.
- Compression that drops `unresolved`, `fact_id` or `rule_id` markers is
  a bug the property tests catch.
- Token savings are never reported when a quality floor fails.
