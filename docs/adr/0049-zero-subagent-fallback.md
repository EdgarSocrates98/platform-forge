# ADR-0049 — Zero-subagent fallback

Status: accepted · cycle 5.1

## Context

Hosts without subagents must not lose evidence or verification.

## Decision

`agents playbook` emits a sequenced human-executable plan carrying the
same evidence requirements, reviewers, and verifier as the agentic
route — enforced by the `host-no-subagents` eval.

## Consequences

Capability degrades in parallelism, not in rigor. A zero-subagent host
still produces a verifiable run.
