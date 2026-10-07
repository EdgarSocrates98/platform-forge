# RULES — the judgment layer

`rules/catalog/*.yaml` — declarative rules evaluated by `RuleEngine`
over `Fact`s. A rule is judgment over evidence, never over prose.

## Shape

```yaml
- rule_id: PF-K8S-001
  domain: k8s
  severity: high
  title: privileged container
  sources: [kubernetes-docs]          # §9 — required, registry-linked
  applies_to:
    fact_kind_prefix: "k8s."          # or fact_kind: [...]
  when:
    all: [{path: attrs.pod_spec.privileged, op: eq, value: true}]
  versions: {}                        # §12 — {product: constraint}
  remediation: ...
```

- `when.all|any|none` predicate lists; ops: eq, neq, in, contains, empty,
  not_empty, gte, lte, exists, matches, any.
- `versions` gates the rule (ADR-0007): unknown version → `version_notes`
  unresolved marker, mismatch → skipped with reason.
- Version-gated rules use `judge --versions '{"kubernetes":"1.29"}'`.

## Findings

Status `passed|violated|skipped`; violated findings carry `evidence`
(non-empty `fact_id` list — enforced), `attrs.sources` from the rule, and
`version_notes` when applicable. `policy list/check` exposes the catalog.

## Coverage & precision

`evals coverage` reports rule↔case coverage (positive/negative/boundary/
unresolved/version); `evals precision` measures the false-positive rate
against the negative corpus. Current: 63 rules, 63/63 covered.
