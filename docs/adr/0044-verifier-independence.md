# ADR-0044 — Verifier independence

Status: accepted · cycle 5.1

## Context

Self-verification is the failure mode that makes agentic runs
untrustworthy.

## Decision

`verify_run` refuses when the producer set equals the verifier set
(`PF-AGENT-INDEPENDENCE`). Router V2 injects `platform-verifier` on
every non-deterministic route; referee resolution never replaces it.

## Consequences

No agent approves its own work. Verification failure is a `refused`
verdict, not a warning.
