# PLATFORM-ANALYTICS — deterministic intelligence engines

All engines live under `platformforge/analytics/` and share one
contract: deterministic aggregates with declared evidence, coverage,
confidence and limitations. No ML claims on counted data; unknown is
never silently zero (adversarial E2/E6).

## Engines

| Module | Answers |
|---|---|
| `history.py` | `HistoryEngine` — unified event timeline + `HistoricalPattern` over windows `24h/7d/30d/90d/custom` |
| `measurement.py` | platform value by **dimension** — adoption, self-service, reliability, cost-efficiency, security posture, DX friction, toil, debt (no opaque score) |
| `goldenpath.py` | adoption, escapes with reasons, per-path outcomes vs off-path |
| `policyintel.py` | per-policy allows/denies/approvals/exceptions/shadows; `candidate_false_positive` only with repeated exceptions **and** successful outcomes |
| `finops_v4.py` | cost hierarchy, unallocated visibility, trends, anomalies, rightsizing, idle resources, unit economics |
| `capacity.py` | per-dimension headroom, `CapacitySnapshot.saturation`, `capacity_risk` |
| `reliability.py` | per-service profiles (MTTR, change-failure, rollback), `fleet_hotspots`, `blast_concentration` |
| `opsanalytics.py` | operation metrics/hotspots, remediation recurrence |
| `dx.py` | team/platform friction (lead time, approval wait, failure) — **team-level only** |
| `debt.py` | platform debt items with evidence + scope |
| `store.py` | SQLite persistence — retention GC, `forget_subject`, secret-refusal |

## Contracts

`AnalyticsDataQuality` — coverage %, freshness, `confidence_cap`.
`PlatformMetric` — one measured value + provenance (scope, window,
source, evidence ids, completeness).

`HistoricalPattern` — `support`, `sample_size`, `confidence` from
support size, `hypothesis`, `limitations` (always includes
"correlation is not causality"). Small samples →
`insufficient-history`, never high confidence.

## Honesty invariants (eval probes + adversarial tests)

- stale events can't seed fresh conclusions (strict windows)
- repeated co-occurrence → hypothesis, never causality
- idle ≠ deletable; low util keeps `deletable: false`
- centrality never assigns `declared_criticality`
- exceptions alone never flag a policy bad (needs outcome evidence)
- missing cost allocation → `unallocated`, missing denominator →
  `unknown`
