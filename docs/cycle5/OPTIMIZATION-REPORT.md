# Cycle 5 — Optimization Report

Measured against `lab/fleets/acme` (the shared 21-member fixture):
`platformforge optimize portfolio lab/fleets/acme`.

## Portfolio (real output)

| Metric | Value |
|---|---|
| total_opportunities | 67 |
| promoted | 21 |
| suppressed | 46 |
| data quality | coverage 0.30 → confidence capped `low` |

Suppression is honest: 46 opportunities stay `high` uncertainty
(thin evidence or unmeasured signals) and are counted, never
silently dropped — `portfolio().suppressed` is part of the answer.

## Top recommendations (by rank_score)

| rec | type | confidence | savings | why |
|---|---|---|---|---|
| opt-2-scan-3 | cost | low | 9800/mo | rightsizing `ml-inference` (cpu 8%, mem 12%, headroom 0.9 — 3 observed signals) |
| opt-4-scan-5 | cost | low | 1750/mo | unallocated cost — allocation coverage gap |
| opt-6-scan-7+ | reliability / security | low | — | hotspots + wildcard-iam/public-services findings from graph questions |

## Boundary verified

- `optimize plan <dir> --id <rec>` emits a `ChangeIntent` doc and
  nothing else — reason `recommendation`, risk_context carries the
  rec's own confidence/risk. No `execute`/`envelope`/`mint` path
  exists in `OptimizationEngine` (adversarial E7, gate
  `optimization`).
- Low coverage caps every recommendation to `confidence: low`
  via `AnalyticsDataQuality.confidence_cap` (§251) — a partially
  observed fleet cannot produce high-confidence advice.

## Where the org should invest (acme evidence)

1. **GPU/ml-inference rightsizing** — largest measured saving
   (~9.8k/mo), three observed utilization signals.
2. **Cost allocation** — 1750/mo unallocated; ratio visible in
   `fleet costs.hierarchy.unallocated_ratio`.
3. **Security questions** — `public-services`, `wildcard-iam`
   findings with fact-cited nodes.
4. **Reliability** — `batch-etl` recurring incident pattern +
   remediation recurrence (root-cause path, not auto-remediate).
