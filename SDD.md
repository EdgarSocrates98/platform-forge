# SDD — native Spec-Driven Development (`platformforge/sdd`)

Lifecycle (each phase = a versioned artifact under `.platformforge/sdd/<FEATURE>/`):

```text
DISCOVER → DEFINE → DESIGN → CONTRACT → PLAN → BUILD → REVIEW → VERIFY → SHIP → LEARN
```

```text
.platformforge/sdd/<FEATURE>/
    discover.md  define.md  design.md  contract.md  plan.md
    build.json   review.md  verify.json  ship.md    learn.md
```

## Artifact frontmatter

```yaml
sdd: 1
feature: <FEATURE>
phase: design
status: draft | ready | stale | accepted
created_at: <utc>
updated_at: <utc>
upstream: {path: <prev-phase-file>, sha256: <hash>}
evidence: []
risks: []
owners: []
```

## Hash cascade

Each artifact records `upstream.sha256`. When `design.md` changes → `plan`,
`build`, `review`, `ship` become `stale`. `platformforge sdd check` reports the
stale set; `sdd stamp` re-seals artifacts after intentional change. Nothing
pretends nothing changed.

## Gates before `ship`

Refuse ship when: a required verification failed · evidence missing · upstream
hash stale · critical finding unresolved · security gate failed · explicit risk
acceptance absent. Overrides emit an override receipt — never silent.

## CLI verbs

`platformforge sdd init|discover|define|design|contract|plan|status|check|
stamp|review|verify|ship|learn`

## Dogfooding

Once stable, Platform Forge's own features are built through this SDD —
small, verifiable artifacts, no ceremony theater.
