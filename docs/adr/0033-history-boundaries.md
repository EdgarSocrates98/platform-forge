# ADR-0033 — Historical intelligence boundaries

Status: accepted · cycle 5

## Context

Historic data is seductive — windows, staleness and support must be explicit or patterns lie.

## Decision

HistoryEngine windows are strict (24h/7d/30d/90d/custom); unparseable ts skipped; patterns need min support; confidence derives from support size only.

## Consequences

Stale data can never seed a fresh conclusion; small samples stay low-confidence.
