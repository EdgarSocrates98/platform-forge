# ADR-0011 — ObservationEnvelope is the single live-ingestion artifact

Status: accepted · cycle 3

## Context

Live collectors produce provider-shaped data. The core must stay
offline, deterministic, and replayable. We need one canonical artifact
that carries not just objects but *how complete and fresh* the
observation is.

## Decision

- Every collection (snapshot or watch-derived) produces a
  `platformforge/observation/v1` envelope: identity, collector, provider,
  `source_type` (observed|runtime), capture/completion/freshness
  timestamps, `scope`, `coverage`, `pagination`, `permissions`,
  `errors`, `cursors`, `resource_versions`, `objects`, `bytes`, `hashes`.
- The core only consumes envelopes (or fixture envelopes). Collectors
  never emit Facts directly — a deterministic extractor converts
  envelopes → facts so `LIVE → ARTIFACT → OFFLINE REPLAY` always works.
- Envelopes are redacted before persistence (cycle §207).

## Consequences

- Adding a provider = one collector + one extractor; no core changes.
- `live doctor`/replay/debug share the same envelope contract.
- Envelope schema is versioned (`observation/v1`) for future evolution.
