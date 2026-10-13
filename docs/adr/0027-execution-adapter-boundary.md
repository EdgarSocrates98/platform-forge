# ADR-0027 — Execution adapters are the only mutation boundary

Status: accepted · cycle 4

## Context

Same boundary logic as collectors: the core decides, adapters act.
Mixing them makes policy and verification optional by construction.

## Decision

- Executors are host-side adapters (`ops/executors/*_transport.py`)
  behind typed action contracts declaring: actions, risk classes,
  dry_run, idempotency, rollback support, permissions, timeouts,
  preconditions.
- Priority order: Git → Terraform/OpenTofu → GitOps → narrow
  Kubernetes. Broad AWS mutation is out of scope for Cycle 4.
- Every execution produces an `ExecutionReceipt`; every mutation is
  hash-pinned to the approved `ExecutionEnvelope` + `idempotency_key`.

## Consequences

- The core stays SDK-free and deterministic; "execution is not an
  agent" — executors receive only typed steps, no LLM context.
