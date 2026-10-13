# OPTIMIZATION — evidence-backed recommendations → ChangeIntent only

`platformforge/optimize/` turns analytics signals into ranked
optimization **recommendations**. It cannot execute anything — the
only bridge to action is `OptimizationEngine.plan()`, which returns a
governed `ChangeIntent` that still passes the full Cycle 4 pipeline
(plan → policy → approve → execute → verify).

## Pipeline

```text
evidence → pattern → OptimizationOpportunity
         → OptimizationRecommendation → ChangeIntent → ops pipeline
```

## Models (`optimize/models.py`)

- `OptimizationOpportunity` — type, scope, evidence, `uncertainty`
  (low|medium|high), estimated savings + unit
- `OptimizationRecommendation` — confidence, evidence, effort +
  `effort_rationale`, verification plan, `priority` (decomposed)

## Promotion rules (spec §294/§303)

`opportunity.promotable()` is honest: **evidence required** and
`uncertainty != "high"`. High-uncertainty or evidence-free
opportunities are suppressed — counted in `portfolio().suppressed`,
never silently dropped.

Confidence is capped by `AnalyticsDataQuality.confidence_cap`; a
`medium`-uncertainty opportunity can never emit a `high`-confidence
recommendation.

## Priority is decomposed — not a score

`priority_of()` returns the dimension tuple (impact / confidence /
effort / risk / scope / evidence-freshness) plus a `rank_score`
derived from them — reviewers see *why*, not just *what*.

## The boundary (adversarial E7)

`OptimizationEngine` has no `execute`/`envelope`/`mint` path.
`plan()` produces `ChangeIntent` with `reason.type="recommendation"`,
`recommendation_ids`, `risk_context` carrying the rec's own
confidence/risk — the ops pipeline re-evaluates everything.

## CLI surface

Bounded: `optimize scan|list|explain|plan` (see CLI-REFERENCE).
