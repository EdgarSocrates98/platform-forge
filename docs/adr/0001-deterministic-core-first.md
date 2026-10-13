# ADR-0001 — Deterministic, offline-first core; LLMs are adapters

Status: accepted · 2026-10-06

## Context

The mission requires platform intelligence that works without any LLM, cluster,
cloud credential, MCP host or internet. Sibling forges prove the pattern
(spark-forge: PyYAML+jsonschema core; api-forge: no provider SDK imports in `src/`).

## Decision

- Core deps: Python ≥3.10, PyYAML, jsonschema, python-hcl2. Nothing else mandatory.
- `boto3`/`mcp`/cloud SDKs exist only as optional extras behind `require_*()`
  guards, called only by collect/adapter layers — never imported by core.
- Evidence tiers T0–T7 stamped on every fact/edge; T6/T7 cannot enter `facts`.
- All persistent payloads are content-addressed (sha256).

## Consequences

The full deterministic pipeline (analyze→judge→graph→report) runs in CI with zero
network. Model-backed composition lives in `platformforge/adapters` and degrades
gracefully to `unresolved` when absent.
