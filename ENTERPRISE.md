# ENTERPRISE — scale, privacy, hardening notes (cycle 5)

This doc collects the enterprise-shape guarantees. Each is enforced
by a gate in `scripts/validate.py` (`fleet-*`, `privacy`,
`adversarial`) — not just asserted here.

## Multi-… without identity collision

Fleets span teams, repositories, services, accounts, clusters,
environments. Member identity is `kind:canonical_id` — deterministic
and collision-free (probe `member-key-deterministic`).

## Coverage-first answers

Every fleet/analytics result carries coverage and keeps
permission-limited/unreachable members listed. `coverage < 1` is
surfaced, never hidden (E1).

## Storage

- `analytics/store.py` — SQLite: events, snapshots, patterns;
  retention `gc(event_days, snapshot_days)`; `forget_subject`
  right-to-forget with receipt; secret-key payloads refused
  (`PF-ANALYTICS-SECRET`); `stats()` self-metrics
- `graph/backend.py` — pluggable `GraphBackend`: memory + SQLite
  baselines, canonical provider-neutral model retained

## Config schema v3

`.platformforge/config.yaml` — `features` domain (fleet, analytics,
optimization, golden_path, ai_platform on; `federation` opt-in),
`privacy` domain pinned (`dx_metrics: team-level-only`,
`person_identifiers: forbidden`, retention days, right_to_forget).
`validate_config` refuses to loosen privacy or telemetry
(`PF-OPS-CONFIG-PRIVACY`, `PF-OPS-CONFIG-TELEMETRY` — telemetry is
pinned `local-only`; no phone-home mode exists).

## Benchmarks

`platformforge bench scale` — measured graph build/merge/deps/blast/
diff/ser/deser/memory + store insert/query/forget/size. Numbers in
`docs/cycle5/SCALE-BENCHMARKS.md`; no scale claim without a number.

## Privacy

DX metrics measure **platform friction at team level** —
`FORBIDDEN_METRICS` (per_person, individual, developer_score,
productivity_score, person_id) can never appear; hostile input with
person fields is dropped and `guard_no_person_metrics` audits the
output (adversarial E10).
