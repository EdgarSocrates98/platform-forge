# ADR-0035 — Platform metric provenance

Status: accepted · cycle 5

## Context

A platform value without provenance cannot be reviewed.

## Decision

PlatformMetric carries metric_id, dimension, scope, window, source, evidence ids, confidence, completeness; value=None renders unknown.

## Consequences

Every displayed number is traceable; unknown stays unknown.
