# OBSERVATION-MODEL — the envelope

`live/models.py` + `contracts/observation.schema.json`. Every live
collection produces one envelope; it is the unit of truth downstream.

```json
{
  "observation_id": "obs-<hash>",
  "provider": "kubernetes",
  "scope": {"cluster": "…", "namespaces": ["…"], "resource_types": ["…"],
            "regions": [], "services": []},
  "collected_at": "…Z",
  "collector_version": "…",
  "coverage": {"attempted": n, "succeeded": n, "denied": n,
               "timed_out": n, "complete": true|false,
               "denial_details": [{"resource_type": "…", "reason": "…"}]},
  "resources": [{"resource_id": "…", "kind": "Deployment",
                 "uid": "…", "namespace": "…", "name": "…",
                 "attributes": {…redacted…}, "labels": {}, "evidence": […]}],
  "ledger": {"api_calls": [{"op": "…", "duration_ms": n, "bytes": n}],
             "budget": {"max_objects": n, "max_api_calls": n, "max_bytes": n,
                        "exhausted": []}},
  "cursor": {"continuation": "…"|null, "resource_version": "…"},
  "warnings": ["…"]
}
```

## Invariants

- **Coverage is explicit.** `coverage.complete=false` whenever a call
  was denied, timed out, or truncated. Consumers check coverage before
  drawing absence conclusions.
- **Freshness is measured.** `collected_at` + a per-consumer freshness
  horizon (`live/reconcile.py --window`, temporal expiry) decides
  whether an observation is still usable. Stale observations are
  reported as `stale-observation`, not "no drift".
- **Provenance per resource.** `evidence` entries carry tier +
  source-ref, same model as facts.
- **Deterministic id.** `obs-<content-hash>` — replaying the same
  fixture yields the same envelope.
- **Store is append-only.** `live/store.py` persists envelopes under
  `.platformforge/observations/<id>.json`; `live status` lists them.
- **Cursors** (`live/cursors.py`) persist continuation state per
  scope-key so incremental collections resume instead of rescanning.

## Absence semantics

| Situation | What gets recorded |
|---|---|
| resource enumerated then absent in later obs | `observed-orphan` drift + `deletion_evidence` |
| resource type denied (403/Forbidden) | `coverage.denied` + `denial_details`; absence of those resources is `unresolved` |
| resource type not in scope | not asserted; `coverage` lists attempted types only |
| observation stale | reconciler emits `stale-observation` verdict |

Never: "not seen" → "does not exist".
