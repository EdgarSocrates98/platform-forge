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
