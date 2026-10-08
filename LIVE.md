# LIVE — Runtime & Live Platform Intelligence

Cycle 3 turns Platform Forge into a live intelligence system: the
platform **as it is actually operating**, not just as declared in IaC
or dumped to files. The hard rule is unchanged — **the core
(`platformforge/`) never does network or SDK IO**. Provider access is a
host-side transport boundary; everything downstream is deterministic,
offline-replayable, and evidence-graded.

## The boundary

```
kubectl / aws CLI (host creds, read-only verbs)
        │  subprocess — the only network boundary
        ▼
platformforge/live/collectors/*.py   normalize → Observation envelope
        ▼
.observations store + provider-call ledger + cursors
        ▼
identity → reconcile → topology → drift → incident → plan
```

- `live/collectors/k8s_transport.py`, `aws_transport.py` — subprocess
  wrappers. Read-only verb allowlist, credential-flag refusal, per-call
  budget accounting. Never imported implicitly; injected or invoked.
- Everything else in `live/` is pure: no imports of boto3/kubectl.
- `--offline` refuses the transports before any subprocess.

## Verbs — `platformforge live`

| Verb | What it does |
|---|---|
| `snapshot` | Collect a live observation (kubectl/aws) → envelope. `--no-store` to skip persistence. |
| `status` | Observation store status (counts, ids). |
| `doctor` | Provider preflight: binary present, auth reachable, per-call permission probe with `--deep`. |
| `rbac` | Emit the minimum `ClusterRole`/`Role` the k8s collector needs (`--namespaced-only`). |
| `required-permissions` | Emit the minimum AWS IAM action list + k8s RBAC for collection. |
| `reconcile` | desired↔planned↔observed↔runtime alignment → drift classes. |
| `topology` | OTel/Hubble/EndpointSlice → runtime edges; `--apply-to-graph` layers evidence onto the graph. |
| `clusters` | Cluster registry (`--register`) + multi-cluster federation view. |
| `drift` | Observation-to-observation diff → deduplicated drift-event journal. |
| `incident` | Canonical timeline + factorized candidate ranking → postmortem V3. |
| `plan` | Drift events → safe remediation plan + approval envelope. Never applies. |
| `capability` | Dynamic capability availability (host prereqs, budgets, provider access). |

Budgets on every collector call: `--max-objects`, `--max-api-calls`,
`--max-bytes` — exhaustion degrades coverage explicitly, never silently.

## Semantics that never bend

- **Absent ≠ deleted.** A resource missing from a scoped observation is
  `unresolved` unless coverage proves full enumeration.
- **Stale ≠ current.** Every envelope carries `collected_at` +
  freshness horizon; reconciliation degrades on stale input.
- **Correlation ≠ causation.** Incident candidates are ranked by named
  factors; `confirmed` requires causal evidence or stays
  `candidate`/`unresolved`.
- **Plan ≠ apply.** `live plan` emits a plan + approval envelope with a
  deterministic hash. There is no `apply` path in the core.
- `planned ≠ observed` always; contradictions surface both sides.

See: OBSERVATION-MODEL.md · COLLECTORS.md · RECONCILIATION.md ·
RUNTIME-TOPOLOGY.md · MULTI-CLUSTER.md · INCIDENTS.md ·
docs/cycle3/FINAL-REPORT.md.
