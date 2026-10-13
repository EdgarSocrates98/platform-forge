# CYCLE 2 — NORTH STAR (§191)

> "Analise minha plataforma" — answered with evidence, not vibes.

## The one-sentence claim

Platform Forge reads the artifacts you point it at and returns a
**truthful, provenance-tagged model** of the platform — what exists,
how it connects, who owns it, what is planned vs observed, what is
secure/reliable/expensive — and it **names what it does not know**
instead of guessing.

## Invariants (the deal it keeps)

1. A `Fact` is an anchored observation; T6/T7 inference never becomes
   a fact. A `Finding` always cites `fact_id` evidence + a `rule_id`
   traceable to a dated source.
2. `planned` ≠ `observed`; `declared` ≠ `measured`; `inferred` is
   labeled. Contradictions surface both states, never a silent winner.
3. Unknown → `unresolved` with an unlock — never zero, never low-risk.
4. Secrets never cross a boundary — facts, context packs, Caveman,
   MCP — enforced by pipeline + property tests.
5. The core never mutates anything. Execution is host-side, behind a
   gate. Chaos is `environment: simulation`; production is refused.
6. Economy is measured (`payload_bytes`, `quality_per_token`); provider
   tokens and savings are `unresolved` unless a transcript supplies them.

## What Cycle 2 actually changed

Cycle 1 shipped the surface. Cycle 2 made it *honest and deep*:
planned/observed separation, rule provenance, version-unresolved
semantics, real flags, real cloud dumps, k8s/gitops depth, golden paths
with evidence, FinOps/security/risk depth, a 34-case eval corpus with
coverage + precision, and the hardening layer — capability contracts,
referee v2, ownership, cross-repo, receipts, explain, recommend, plan
DAG — all verified, all measured.

## Where it stops (the boundary it keeps)

It does not deploy, does not escalate credentials, does not call a live
cloud, does not certify production readiness, and does not invent a
number it did not measure. The gaps are `planned`/`partial`/`foundation`
in the roadmap — stated, not hidden.
