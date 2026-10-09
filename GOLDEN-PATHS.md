# GOLDEN PATHS — paved roads with evidence, not just templates

A golden path is three things (ADR-0010): a scaffold, guardrails
(rules), and signals the platform can measure. §76 — it is never only
a template.

## Model (§74)

```yaml
golden_path:
  id: service-python
  scaffold: {...}                 # template layout
  guardrails: [PF-* rule ids]     # what "on the path" means
  signals: [...]                  # measurable adoption/conformance
  escape_hatch: allowed           # deviations are named, not blocked
```

`product/golden_paths/` ships the engine + seed library.
`product paths` lists the library, `product path <id>` describes one,
`product capabilities` emits the machine-readable self-service surface.

## Scoring (§78)

`product path-analyze --facts <facts.json>` scores an estate:

- `coverage` — which declared signals were observed in facts.
- `conformance` — which guardrail rules passed.
- Unknown signals are `unresolved`, never zero (§80 — maturity v2
  separates `observed` vs `declared`; `overclaimed` is a finding).

## Self-service contract (§79)

`product capabilities` returns the path's declared scaffold + guardrails
+ evidence hooks — a contract a portal can render. The core does not
write files; scaffolding execution is host-side.

## Escape hatch (§77)

Deviations are first-class data: a repo may declare
`golden_path.deviation` with a reason; the report records it as a
labeled deviation, not a violation.
