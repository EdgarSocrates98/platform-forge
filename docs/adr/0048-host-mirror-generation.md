# ADR-0048 — Host mirror generation

Status: accepted · cycle 5.1

## Context

Per-host agent files drift the moment they're hand-edited.

## Decision

`agents/mirrors.py` renders the canonical roster to `agents/`,
`.agents/agents/`, `.claude/agents/`, `.codex/agents/`, `.devin/agents/`
(205 files). `agents check` diffs generation state and fails on
missing/stale/stray.

## Consequences

Mirrors are a build artifact. Permissions cannot leak into a host
mirror that the contract doesn't grant.
