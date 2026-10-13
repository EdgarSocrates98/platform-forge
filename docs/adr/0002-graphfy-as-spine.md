# ADR-0002 — Graphfy as the integration spine

Status: accepted · 2026-10-06

## Context

Platform questions are dependency questions that cross repo and provider
boundaries (repo→CI→image→GitOps→K8s→network→cost→owner). Without a shared graph
each domain analyzer is an island.

## Decision

- `platformforge/graph` is infrastructure, built before domain sprawl (Phase 4).
- Facts produce nodes/edges 1:1; edges carry `provenance`, `confidence`,
  `source_fact_ids` — inferred ≠ observed, enforced in the model.
- `workspace.yaml` joins multiple repos (app/infra/gitops) into one graph.
- Backstage catalog entities are an import/export projection of the graph,
  never the canonical store.

## Consequences

Blast radius, impact, ownership gaps, cost allocation, SLO coverage and
supply-chain traversal become the same traversal code with different filters.
