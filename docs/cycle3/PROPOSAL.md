# Cycle 3 — Runtime & Live Platform Intelligence (concept)

**Status: proposed — no implementation.** This document is the concept
for the next cycle, per the 2.1 closure contract. Nothing here ships in
Cycle 2.1.

## Why

Today the platform analyzes *declared* and *planned* state — manifests,
IaC, dumps. The gap is the *observed* side: what is actually running,
right now, and how it differs from intent.

## Scope sketch

- **Live discovery** — host-side collectors for Kubernetes (API server
  inventory) and AWS (read-only resource enumeration), producing T1
  observed facts. Collectors stay outside the core (the core keeps its
  no-SDK boundary); dumps remain the transport.
- **Continuous reconciliation** — desired (repo) vs planned (plan) vs
  observed (live inventory) as a three-way comparison with named
  drift classes, not a boolean.
- **Runtime topology** — live edges: which pods actually talk to which
  services, which workload assumed which role, which bucket is actually
  public today.
- **Multi-cluster** — per-cluster views + a federation layer that
  preserves provenance per source.
- **Live drift** — diff snapshots over time; drift alerts feed incident
  correlation rather than a flat diff list.
- **Incident correlation** — join live topology + recent changes +
  open incidents; rank candidates by blast radius over *observed* edges.
- **Controlled remediation planning** — propose the change, compute the
  delta, route to approval — never apply (read-only boundary kept).

## Non-goals (carried forward)

- No provider SDK imports in the core; no live mutation.
- No "apply/remediate" verbs — the host executes; the platform reviews.
- No observability vendor lock-in — live signals arrive as dumps or
  stdin, not via credentials held by the core.

## Open questions for the spec phase

- Freshness model: pull on demand vs scheduled snapshot vs event-fed?
- Identity: how do observed identities map to declared principals
  without a live IdP lookup?
- Cardinality: multi-cluster × live drift × incident streams — what
  gets sampled, and what's the refusal when sampling hides signal?
