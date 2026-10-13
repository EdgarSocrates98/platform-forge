# ADR-0007 — Unknown versions produce unresolved notes, not verdicts

Status: accepted · cycle 2

## Context

A version-gated rule (e.g. `apps/v1beta1` removed in Kubernetes 1.22)
cannot be evaluated without knowing the target version. Treating an
unknown version as compliant invents safety.

## Decision

- `rule.versions` declares `{product: constraint}`.
- `version_satisfies` returns `True|False|None`; `None` (unknown) keeps
  the rule evaluable but stamps `version_notes:
  platform.version.unresolved:<product>(<constraint>)` on the finding.
- `False` skips the rule with a named reason (`version-mismatch`).
- `judge --versions '{"kubernetes":"1.29"}'` supplies declared versions;
  MCP `platformforge_analyze`/`judge` accept the same input.

## Consequences

Version-dependent findings always expose their epistemic state. The eval
corpus has `version`-typed cases covering fire/skip/unresolved.
