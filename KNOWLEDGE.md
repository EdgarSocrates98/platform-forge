# KNOWLEDGE — source registry & freshness

Platform Forge never freezes tool knowledge. `knowledge/sources.yaml` is
the registry; `platformforge knowledge` reports freshness.

## Entry contract (§46)

Each source entry: `id`, `source` (URL), `source_authority` (§145
priority: official spec > vendor docs > official GitHub release >
foundation docs > secondary), `retrieved_at`, `product`, `version`,
`confidence`, plus `deprecated`/`superseded_by`/`valid_from`/
`valid_until` when applicable.

## Freshness (§47)

`SourceEntry.freshness()` returns `current|fresh|stale|deprecated|
superseded|conflicted|unresolved` — computed from `retrieved_at`
(FRESH_DAYS=120, STALE_DAYS=365), never assumed.

## Rule linkage (§44, cycle 2.1)

Every rule's `sources:` is a list of **canonical registry ids** — exact
`SourceRegistry.get()`/`resolve()` lookup, no domain-suffix inference (a
`k8s.io` rule must never silently match `gateway-api.sigs.k8s.io`).
Doc path/anchor detail lives in `source_refs: {id: path#anchor}`, and
every `source_refs` key must appear in `sources`. `aliases:` on a
registry entry are the only escape hatch — declared, never inferred.
The linkage gate reports `unlinked` rules and dangling `bad_refs`;
CI requires coverage = 1.0 and both lists empty.

## Research ledger (§146)

A new specialization lands only with its source entries updated — source,
retrieved_at, version, what was learned, which capability uses it.

## Knowledge packs (cycle 2.1 §60–68)

`sources.yaml` is the provenance registry. Packs under
`knowledge/<domain>/<id>.yaml` are the operational layer — claims that
rules and analyzers actually consume:

```yaml
schema: platformforge/knowledge/v1
id: kubernetes-api-deprecations
domain: kubernetes
applies_to: {versions: [kubernetes]}
sources: [kubernetes-docs]            # canonical ids, resolved exactly
claims:
  - id: k8s-dep-v122
    statement: "..."
    versions: {kubernetes: ">=1.22"}
used_by:
  rules: [PF-K8S-030, PF-K8S-031, PF-K8S-032]
  analyzers: [k8s]
```

`knowledge packs` lists packs with `content_hash` (sha256 of the canonical
claim set — drift detection, §68). `contract_check` resolves every
`sources` id against the registry, every `used_by.rules` against the
catalog, every `used_by.analyzers` against the analyzer table, and flags
packs nothing consumes. `knowledge packs --strict` exits 2 on any
violation; CI enforces it.

Current packs (§123 — only mature domains): kubernetes (api-deprecations,
pod-security, gateway-api, autoscaling-rbac), aws (iam, network-exposure,
organizations, eks), terraform (plan-semantics, lifecycle), crossplane
(managed-resources, v1-vs-v2, composition-providers).
