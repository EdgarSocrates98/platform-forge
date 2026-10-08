# ADR-0014 — Freshness and coverage are separate, per-domain configurable

Status: accepted · cycle 3

## Context

A fresh partial snapshot and a stale complete snapshot are different
failure modes; conflating them corrupts reconciliation verdicts.
Universal TTL constants would be wrong across domains.

## Decision

- `coverage_status` ∈ complete|partial|sampled|truncated|
  permission-limited|unsupported|unknown — independent axis from
  `freshness_status` ∈ fresh|aging|stale|expired|unknown.
- Freshness derives from `captured_at` + `fresh_until` (per-domain
  config; no universal defaults).
- Expired observations cannot support strong current-state verdicts;
  they downgrade conclusions to `stale-observation`/`unresolved`.

## Consequences

- Referee/arbitration can prefer fresh-over-stale evidence and preserve
  both (cycle §233).
- Reconciliation reports temporal skew explicitly (§234–236).
