# ADR-0005 — Redaction is a pipeline boundary, not a formatter

Status: accepted · cycle 2

## Context

Secret values must never cross context, compression or MCP boundaries —
even when a tool output forgets to redact.

## Decision

- `core/redaction.py` is the single redaction engine; every boundary calls
  it: TokenSave index bodies, Caveman compress (including mode `off`),
  MCP tool output (deep `redact_obj` before serialization).
- Redactions emit a receipt (`redaction_receipt`) recording count and
  labels — never the values.
- Property tests assert a known secret never appears in a ContextPack,
  MCP response, Finding or Caveman output.

## Consequences

Redaction is defense-in-depth: analyzer-level, context-level and
transport-level. A leak in one layer is caught by the next.
