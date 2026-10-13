# ADR-0055 — Context Gateway as the single context entry point

Status: accepted · economy cycle (FE-002)

## Context

Context assembly was scattered — each caller hand-picked facts, so budgets were advisory and nothing proved what a model saw.

## Decision

All model/agent context goes through ContextGateway: scope → evidence selection → dedup → budget → pack → redact → ContextRef. Output is a ContextCapsule plus context://sha256/ refs; sections expand lazily; sufficiency (sufficient/partial/insufficient) is measured, and insufficient context refuses rather than answers confidently.

## Consequences

Callers get bounded, redacted, auditable context; the gateway — not each agent — owns the essential-evidence floor (PF-CONTEXT-ESSENTIAL).
