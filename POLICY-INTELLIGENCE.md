# POLICY-INTELLIGENCE — what the policies actually do over time

`platformforge/analytics/policyintel.py` analyzes historical policy
decisions: allows, denies, `require-*` approvals, exceptions,
expired exceptions, shadow decisions, overrides.

## Metrics

`policy_metrics(decisions, exceptions, overrides)` → per-policy
distribution: `evaluations`, `allows`, `denies`,
`requires_approval`, `shadow_decisions`, `exceptions`,
`expired_exceptions`, `overrides`, `most_common`, `stale` (a
configured policy that never fires is stale — maybe dead code).

## candidate_false_positive — evidence-gated

`false_positive_candidates(metrics, outcomes)` flags a policy only
when **three** things co-occur (§52):

1. repeated exceptions (`>= min_support`)
2. repeated successful outcomes after override (`>= min_support`)
3. enough support for confidence

The flag is `candidate_false_positive` with
`verdict: review-required` — **never** an automatic verdict, never
an enforcement change (adversarial E5: exceptions alone with zero
successful outcomes → no flag).

## Recommendations

`policy_recommendations` emits typed actions only: `tighten`,
`relax`, `split-scope`, `convert-to-warning`,
`add-exception-pattern`. Every one carries `executes: false` and
`review-required` — humans change policy, never the engine.
