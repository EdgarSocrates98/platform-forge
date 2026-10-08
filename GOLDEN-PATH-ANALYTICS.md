# GOLDEN-PATH-ANALYTICS — adoption, friction, escapes

`platformforge/analytics/goldenpath.py` measures whether golden
paths actually get used — and why not.

## Analytics

`golden_path_analytics(requests, outcomes, escapes)` → per-path:

- `requested / provisioned / failed` + `success_rate`
- lead time (`requested_at` → `ready_at`) and `approval_wait_s`
- `escape_reasons` histogram — `policy-block`,
  `insufficient-flexibility`, `manual-preference`, …
- outcome comparison on-path vs off-path (incident/rollback rates) —
  worse outcomes are reported as **hypothesis**, not verdict
  (correlation ≠ causality)

## Graph evidence

`uses_golden_path` / `escapes_golden_path` edges in the org graph
are `organizational` impact class — a service outside the golden
path is an adoption finding, not a blast-radius claim.

## Recommendations

`golden_path_recommendations` proposes fixes only — e.g. "investigate
policy-block escapes on path X", "path Y has failed provisions" —
each with evidence counts. It never retires a path automatically
and never scores the teams that escaped it.
