# ADR-0015 — Graphfy v2: multi-layer evidence, temporal fields, explicit migration

Status: accepted · cycle 3

## Context

v1 merges duplicate edges: one provenance field means a declared edge
later seen at runtime loses its declared evidence (cycle §86–89). Runtime
needs first/last_seen windows. Readers of v1 must not break silently.

## Decision

- `platformforge/graph/v2`: edges gain `evidence[]` — one record per
  layer {provenance, source_type, fact_ids, observed_at} — plus
  `temporal{}` {first_seen, last_seen, window_start, window_end,
  sample_count} for runtime edges.
- `effective_provenance` remains the computed strongest layer; all
  contributing layers stay queryable.
- Explicit `v1 → v2` migration; v2 reads v1 (evidence synthesized from
  the single provenance); round-trip tests mandatory.
- Runtime edges expire (mark `not_recently_observed`) — history is never
  deleted (§91).

## Consequences

- "Declared + observed at runtime" is expressible and preserved.
- Temporal queries ("at T1?", "between T1 and T2?", "when did this edge
  appear?") become first-class.
