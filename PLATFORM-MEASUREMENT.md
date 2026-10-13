# PLATFORM-MEASUREMENT — value by dimension, never one score

`platformforge/analytics/measurement.py` answers "is the platform
good?" with decomposed dimensions. There is deliberately **no global
maturity score** — an opaque number would hide the evidence.

## Dimensions

| Dimension | Inputs |
|---|---|
| `adoption` | services on golden paths vs total |
| `self_service` | provisioned-without-ticket ratio |
| `reliability` | incident counts, SLO coverage |
| `cost_efficiency` | idle %, unallocated %, unit economics |
| `security_posture` | open findings by severity, exposure |
| `developer_friction` | lead time, approval waits (team-level) |
| `operational_toil` | manual ops, remediation recurrence |
| `platform_debt` | debt items with evidence |

Each dimension carries `value`, `confidence`, `coverage`, `evidence`
and `limitations` — a dimension with thin coverage stays `unknown`
rather than faking precision.

## Maturity V3 diagnostics

Maturity is reported **per dimension** (foundation / partial /
implemented / validated / lab-validated / production-validated) —
matching the closure matrix levels. `production-validated` is never
self-declared; it requires evidence of real use.

## Contract

`PlatformMetric(metric_id, dimension, scope, value, unit, window,
source, evidence, confidence, completeness)` — every number keeps
its provenance; `value: None` + completeness `None` renders as
`unknown`.
