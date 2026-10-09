# ADR-0054 — Multilayer cache invalidation

Status: accepted · economy cycle (FE-002)

## Context

Cached facts went stale silently when rules changed — a finding cached under rule-catalog v1 was served under v2.

## Decision

Seven layers (artifact/fact/graph/finding/context/analysis/decision), each bound to declared dependency keys; a dep change invalidates only the layers that bind it (rule change: facts hit, findings miss). Entries are content-addressed, TTL'd, GC'd, and secrets are refused at put. Every reuse emits a receipt.

## Consequences

Reuse is safe by construction; stale conclusions cannot masquerade as fresh. The analysis layer stayed dark until invalidation tests passed.
