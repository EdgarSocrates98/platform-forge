# Context Gateway

`platformforge/context/` — the single entry point for all model/agent
context. ADR-0055.

## Pipeline

```text
Task → Scope → Search* → Graph expansion* → Evidence selection →
Dedup → Budget → Pack → Redaction → ContextRef
```

*Search/expansion inputs arrive already extracted — the gateway
assembles; it does not analyze.

## Contracts

`ContextRequest(task, scope, budget_bytes, essential_bytes,
required_sections, role, query, facts, findings, rules, knowledge_refs,
graph_refs, artifact_refs, open_questions, deps)` →
`ContextCapsule` persisted under `.platformforge/context-store/`,
addressed by `context://sha256/<hash>`.

## Sufficiency

`sufficient | partial | insufficient` — measured from required vs
present sections. `insufficient` forbids confident answers; when
`essential_bytes > budget_bytes` the build refuses with
`PF-CONTEXT-ESSENTIAL` instead of truncating evidence.

## Lazy expansion

Capsule `expandable` maps section → context:// ref; `expand(ref,
section)` returns just that section. Role views (`for_role`) narrow a
stored capsule to what the role needs — a verifier gets criteria +
evidence + receipts, never a transcript.

## CLI / MCP

`context capsule|inspect|expand|delta|gc`;
MCP: `platformforge_context_inspect`, `platformforge_context_expand`
(read-only).
