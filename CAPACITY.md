# CAPACITY — headroom, saturation, fleet risk

`platformforge/analytics/capacity.py` reports capacity by dimension
per fleet member — with honest unknowns.

## Model

`CapacityDimension(name, used, capacity, source)` →
`headroom = (capacity - used)/capacity`, or `None` when data is
missing (`source: unavailable`). Unknown headroom is reported as
`unknown` — **never rendered as 0% or 100%** (adversarial E1/E6).

`CapacitySnapshot(member_id, dimensions)` → `saturation()` lists
`saturated_dimensions` (headroom < 15%), `unknown_dimensions`,
overall `headroom_state`.

## Risk

`capacity_risk(snapshot, criticality, failure_domains)` →
`low|elevated|high` with the factors that produced it. High requires
saturation **plus** context (declared criticality, single failure
domain) — raw saturation alone is `elevated`, not a crisis.

## Forecasts

`forecast(points)` returns levels only:

- `insufficient-history` below minimum samples — no fake prediction
- `trend` with measured slope when data exists

## Fleet view

Capacity scenarios (`lab/scenarios/fleet-capacity`) exercise
multi-member saturation, GPU pools, and permission-limited members
whose headroom stays `unknown`.
