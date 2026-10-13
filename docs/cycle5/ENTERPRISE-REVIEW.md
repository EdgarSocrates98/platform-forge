# Cycle 5 — Enterprise Review

Organizational-scale review of the cycle-5 surface. Each claim is
backed by a gate or probe — see VALIDATION-RECEIPT.json.

## Multi-scope identity

`member_key(kind, canonical_id)` is the only identity — deterministic
and collision-free across teams/envs/accounts (probe
`member-key-deterministic`). 21 members in `lab/fleets/acme` span
3 teams, 6 clusters, 2 cloud accounts, 4 environments without a
single collision.

## Coverage-first conclusions

`FleetSnapshot.coverage` = min member coverage; `coverage_ratio`
keeps permission-limited/unreachable members listed. A 5/6 fleet
cannot produce a "complete" verdict — lab scenario
`fleet-partial` + adversarial E1 enforce it.

## Federation posture

- `features.federation` defaults **off** (config v3) — the boundary
  is opt-in.
- `export_summary` is fail-closed: unmapped classifications deny;
  secret-shaped payloads deny at *every* classification
  (`PF-FED-SECRET-BOUNDARY`).
- `federated_query` returns per-node answers + coverage +
  "no execution authority crossed the boundary" (E8/E9).

## Delegation refusals (preserved)

`direct-execution`, `approval-minting`, `shell-command`,
`generic-provider-call`, `full-fleet-dump`, `credential-transfer`
→ `PF-OPS-CROSSFORGE-REFUSED` + `unlock`.

## Config & privacy pins (schema v3)

`validate_config` refuses telemetry loosening
(`PF-OPS-CONFIG-TELEMETRY` — pinned `local-only`) and privacy
weakening (`PF-OPS-CONFIG-PRIVACY` — dx `team-level-only`,
person identifiers `forbidden`). Migration 0→1→2→3 verified
(`test_migration_v0_to_v3`).

## Storage lifecycle

`AnalyticsStore` (SQLite): retention `gc(event_days, snapshot_days)`,
`forget_subject` right-to-forget with receipt, secret-refusal on
ingest (`PF-ANALYTICS-SECRET`), `stats()` self-metrics.

## Declared gaps (honest)

- No MCP tools expose cycle-5 surfaces yet (MCP.md).
- `fleet drift`/`analytics` need event inputs — empty sources
  produce `unknown`/empty, never fabricated patterns.
- `federation` assumes nodes are reachable out-of-band; transport
  is the host's job.
