# ADR-0040 — Pluggable analytics storage

Status: accepted · cycle 5

## Context

Analytics need persistence; the backend must stay swappable and offline.

## Decision

AnalyticsStore (SQLite) persists events/snapshots/patterns with retention GC + forget_subject + secret-refusal; GraphBackend contract (memory, sqlite) keeps the graph backend pluggable.

## Consequences

Storage is local and durable; right-to-forget is executable; backends can be replaced without changing engines.
