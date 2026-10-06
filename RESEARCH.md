# RESEARCH — Platform Forge technical ledger

Retrieved 2026-10-06. Every entry cites `knowledge/sources.yaml` IDs. Nothing here
is treated as eternal truth — `platformforge knowledge check` re-verifies freshness
and marks entries `current | fresh | stale | deprecated | superseded | conflicted |
unresolved`.

## Verified findings (version-bearing)

| Fact | Value | Source |
|---|---|---|
| CNCF Platform Engineering Maturity Model | v1.0 (2023-11). 5 aspects: Investment, Adoption, Interfaces, Operations, Measurement. 4 levels: Provisional, Operational, Scalable, Optimizing. | `cncf-maturity-model` |
| SLSA | v1.2 current. Two tracks: **Build** (provenance trustworthiness) and **Source** (L1 versioned, L2 history+provenance, L3 continuous controls, L4 two-party review). | `slsa-spec` |
| FOCUS | Latest listed 1.4; v1.2 ratified 2025-05-29 adds SaaS/virtual-currency columns (pricing currency, effective cost, contracted pricing in credits/tokens). | `focus-spec` |
| Karpenter | v1 API stable since 2024-08; v1beta1 NodePool concepts superseded — version-gate autoscaling rules. | `karpenter-docs` |
| Crossplane | v2 line changed XR/claim model (namespaced XRs, no default claim) vs v1 — composition rules are version-gated. | `crossplane-docs` |
| Kyverno | Current releases add CEL-based policy types (ValidatingPolicy, ImageValidatingPolicy…) alongside legacy ClusterPolicy — both families modeled. | `kyverno-docs` |
| Kubecost | Docs now hosted under IBM (post-Apptio acquisition); URL churn expected. | `kubecost-docs` |
| Vault | HashiCorp Vault is BUSL ≥1.1.x; OpenBao is the community fork — cite both in recommendations. | `vault-docs` |

## Domain conclusions for architecture

1. **Platform engineering is product-shaped.** DORA + CNCF converge on:
   platform-as-product, golden paths, self-service, measured adoption. → the
   `platform_product` domain is first-class, not a plugin.
2. **Evidence tiering is the differentiator.** Neither sibling Forge nor any OSS
   analyzer confuses observed runtime state (T0/T1) with declared config (T3) —
   Platform Forge makes the tier explicit on every fact and edge.
3. **Graphfy is the core asset.** Cross-repo/platform dependency (repo→CI→image→
   GitOps→K8s→network→DNS) only exists if the graph crosses repo boundaries —
   `workspace.yaml` multi-repo is a Phase-4 concern, not an afterthought.
4. **Maturity assessment is our own model** inspired by the 5×4 CNCF grid
   (licensing-safe, documented in `docs/platform-maturity.md`).
5. **Economy is architectural**: cache → parse → index → rule → graph → local
   composition → model. LLMs are adapters, never required for deterministic work.

## Out of scope (explicit product decisions)

- No LLM/embedding runtime dependency in the core.
- No direct cloud mutation from the core (read-only default; mutations future,
  gated: dry-run → plan → explicit `--execute` → receipt).
- No replacement of Security Forge; platform security only.
- Backstage/Crossplane/Kubernetes/AWS are optional domains, never mandatory.
