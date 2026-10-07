# QUALITY-PER-TOKEN — measured economy, not asserted savings

§30–32, ADR-0008. Economy claims are evidence-bound: we measure what a
context pack preserves per byte spent, on the same task, and report both
sides.

## The metric

`economy qpt --task <t> --input-budget <n>` runs the task twice:
`full` context vs `tokensave` pack, then reports

```text
quality_per_token = evidence_preserved / tokens_spent
```

with `evidence_preserved` = completeness of fact_ids, rule_ids, risks
and unresolved markers the pack kept vs the full input.

## Corpus (§126)

Realistic tasks in the eval corpus (`token_economy` cases): Terraform
review, Kubernetes review, incident analysis, IAM review, GitHub
Actions review. Floors assert *critical evidence survives*, not a ratio.

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
