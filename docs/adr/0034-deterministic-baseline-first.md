# ADR-0034 — Deterministic baseline first, no fake ML

Status: accepted · cycle 5

## Context

Counts over labeled data are honest; ML labels on arithmetic are not.

## Decision

All analytics are deterministic aggregates (counts, ratios, moving averages, z-scores); each output declares method + confidence; 'model' claims are out of scope.

## Consequences

Reproducible answers; no unexplained scores; upgrading to real ML is a future explicit decision.
