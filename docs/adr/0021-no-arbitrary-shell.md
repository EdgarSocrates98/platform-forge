# ADR-0021 — No arbitrary shell autonomy

Status: accepted · cycle 4

## Context

The easiest path to "operations" is `shell(command: str)` — and it is
the exact failure mode this cycle exists to prevent: an LLM emitting
unbounded commands is an unaccountable mutation channel with no policy,
no verification, no rollback.

## Decision

- All mutation flows through structured typed actions
  (`git.open_pr`, `terraform.apply_saved_plan`, `kubernetes.scale`,
  `argocd.sync`…) executed by deterministic adapters — never through a
  generic `shell.run` action, which does not exist in the vocabulary.
- The pipeline `intent → plan → simulate → risk → policy → approval →
  envelope → preconditions → execute → verify` has no implicit skip.
- Internally a host transport may wrap `git`/`terraform`/`kubectl`
  subprocesses, but only behind the typed-action schema and allowlist
  — the same boundary pattern collectors already use.

## Consequences

- Anything that cannot be expressed as a typed action is refused
  (`PF-OPS-UNSTRUCTURED`), not approximated with a shell call.
- Executor capabilities are enumerable, testable, and auditable.
