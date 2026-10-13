# ADR-0039 — AI workload platform boundary

Status: accepted · cycle 5

## Context

AI workloads are platform resources (GPU, cost, capacity) — model management is not.

## Decision

aiplat detects GPU/serving workloads from declared resources; unit economics emit only with observed denominators; no model registry/serving control plane.

## Consequences

Platform questions answered honestly; no cost/token without tokens; no AI Forge scope creep.
