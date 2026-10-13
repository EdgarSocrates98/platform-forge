# Freeze lifecycle (§5)

```text
OPEN DEVELOPMENT
      │  feature expansion allowed
      ▼
FREEZE CANDIDATE
      │  gates green + manifest written
      ▼
ARCHITECTURE FROZEN          ◄── we are here
      │  dogfooding + evidence collection
      ▼
DOGFOODING
      │  F0/F1 resolved, receipts bound to final SHA
      ▼
RELEASE CANDIDATE
      │
      ▼
STABLE
```

## Allowed during freeze (no review needed)

| Class | Examples |
|---|---|
| `bug-fix` | wrong verdict, crash, incorrect extraction |
| `performance-fix` | hot-loop optimization with a benchmark receipt |
| `security-fix` | boundary, redaction, traversal fixes |
| `knowledge-update` | source freshness, catalog corrections |
| `new-eval` | cases that grade existing behavior |
| `new-real-world-fixture` | sanitized replay fixtures |
| `compatibility-update` | new Python/k8s/Terraform version support |
| `documentation` | always allowed; never claims beyond evidence |

## Requires a freeze review (FeatureException, §6)

- new major subsystem
- new public schema family
- new autonomy level
- new control plane
- new domain pillar
- large agent-roster expansion

Submit: `docs/freeze/exceptions/<id>.json`, validated by
`platformforge freeze exception --spec <file>` and the
`freeze-exceptions` gate. Approval requires a named
`real_world_blocker` and evidence — "because it's cool" is an
explicit non-reason (§210).

## Unfreeze (§208–209)

Only on: a proven real-world blocker, a major ecosystem evolution, or
a new required platform paradigm — via an RFC in
`docs/freeze/rfc/` using `UNFREEZE-RFC.md` as the template.
