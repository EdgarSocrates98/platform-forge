# FLEET — fleets, members, snapshots

A **fleet** is the organization's whole platform surface: clusters,
cloud accounts, repositories, services, teams — across environments.
Contracts live in `platformforge/fleet/models.py` (schema
`platformforge/fleet/v1`).

## Contracts

| Type | Role |
|---|---|
| `Fleet` | registered members by kind + ownership/labels/policies |
| `FleetMember` | one member — `kind`, `canonical_id`, environment, labels |
| `MemberObservation` | per-member `status` (observed / permission-limited / unreachable / stale), `coverage`, `freshness` |
| `FleetSnapshot` | point-in-time coverage report — `coverage` ∈ [0,1], `coverage_ratio` text |

Member identity is deterministic: `member_key(kind, canonical_id)` →
`"cluster:prod-1"`. Two members with different kinds never collide.

## Coverage is part of every answer

A fleet conclusion is only as good as what was observed. Snapshots
keep permission-limited and unreachable members **visible** — partial
data never renders as complete (adversarial E1). `coverage < 1`
travels with the result; unknown members are listed, not dropped.

## Fleet questions (`platformforge/fleet/query.py`)

Deterministic graph queries over the org graph — each returns node
ids + `fact_ids` evidence:

`public-services` · `critical-services` · `unsupported-k8s` ·
`wildcard-iam` · `unowned` · `no-slo` · `outside-golden-path` ·
`idle-high-cost` · `cross-env-deps`

Unknown question → `ValueError`; answers cite source facts.

## Org graph projection

`fleet/orggraph.py` projects members into layers — organization,
platform-product, application, infrastructure, runtime, operations,
cost, policy (`layer_of`). Organizational edges (`owns`,
`funded_by`, `uses_golden_path`…) use the `organizational` impact
class so ownership ≠ technical blast radius.

## Feature flag

`features.fleet` (config schema v3, default on). Offline-first:
fleet analytics never need provider credentials.
