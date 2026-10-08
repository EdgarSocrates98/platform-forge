# RECONCILIATION — desired ↔ planned ↔ observed ↔ runtime

`live/reconcile.py` + `live identity.py` + `platformforge live reconcile`.

## Inputs

- **desired** — facts from repo scan (`--desired`, or workspace default).
- **planned** — plan-phase facts (`--planned`, tfplan normalized).
- **observed** — observation envelope id or file (`--observed`), or
  `--no-observed` for desired↔planned only.
- **runtime** — runtime edges already layered on the graph (Phase G).

## Identity resolution (`live/identity.py`)

Strong identifiers first — k8s `uid`, AWS ARN/account+id, Terraform
address. Weak candidates (`kind:namespace:name`, `name`-only) are
accepted only when unambiguous in both sides; ambiguous weak matches
produce `identity.conflict` with both candidates — never a silent
merge. `EKS↔k8s`, `SA↔IAM` cross-provider correlation uses explicit
rules (role annotations, cluster→account mapping), reported as
`identity.correlated`.

Matching consults the **full index** — uid, ARN, TF address,
`kind:ns:name` — not just `resource_id`, so a resource identified
differently across layers still matches.

## Drift classes (verdicts)

| Verdict | Meaning |
|---|---|
| `aligned` | declared ↔ observed agree on compared attributes |
| `config-drift` | shared attribute values differ (replicas, image, port…) |
| `security-drift` | security-class attributes differ (encryption, public, IAM) |
| `desired-missing-observed` | declared but not in observation scope |
| `observed-orphan` | observed but undeclared (or deleted from desired) |
| `planned-not-applied` | plan diverges from observed |
| `runtime-undeclared` | runtime edge has no declared/observed backing |
| `stale-observation` | observation older than the freshness window |
| `unresolved` | coverage insufficient to judge (denied/partial) |
| `accepted-drift` | `drift.allowlist` marks the divergence intentional |

## What it refuses to claim

- A deletion when coverage is partial or the resource type was denied.
- "No drift" on a stale observation.
- Cross-layer equality from weak identity alone when ambiguous.

Determinism: same inputs → same verdict list, same order (sorted).
