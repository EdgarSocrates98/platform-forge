# ADR-0032 — Organizational Graphfy layers

Status: accepted · cycle 5

## Context

Ownership/funding/capability relations are not technical dependencies — mixing them corrupts blast radius.

## Decision

Org edges (owns, funded_by, uses_golden_path, supports...) get impact_class=organizational; layer_of maps kinds to 8 layers; blast/path queries may filter by class.

## Consequences

Ownership ≠ blast radius; org queries exist alongside technical ones.
