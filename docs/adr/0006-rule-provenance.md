# ADR-0006 — Every rule cites a dated source

Status: accepted · cycle 2

## Context

A rule without provenance is an opinion. Findings derived from unsourced
rules cannot be challenged or refreshed.

## Decision

- Every catalog rule carries `sources:` pointing at
  `knowledge/sources.yaml` entries (official docs/specs first, §145).
- `catalog_provenance_report` gates CI: rule coverage must be 1.0.
- Findings propagate `attrs.sources` from the rule.
- `knowledge` freshness check flags stale/unresolved/conflicted sources.

## Consequences

When Kubernetes or Kyverno deprecates an API, the linked source entry
ages out and the drift check surfaces it — the rule is questioned, not
silently trusted.
