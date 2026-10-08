# CYCLE 4 — BASELINE

Audited before implementation. `main` @ `bbddbad` (docs wave pushed).

## What actually exists (verified by running, not assumed)

- **Tests**: 411 pass · **Evals**: 48 pass · **Lab**: 17 pass (live-kind
  gated `kubernetes`) · ruff clean · docs-drift green.
- **Core**: 18,368 LOC under `platformforge/`; SDK-free, network-free
  (`tests/test_offline.py` blocks sockets at syscall level).
- **Graphfy**: v2 graph — multi-layer edge evidence, `temporal.
  {first_seen,last_seen,expired}`, event ledger, v1→v2 migration;
  `edges_between`, `expire_stale_edges` (mark-not-delete).
- **Live intelligence** (`platformforge/live/`): ObservationEnvelope +
  store + cursors + provider-call ledger; k8s/aws read-only collectors
  (subprocess transports, verb allowlists, credential-flag refusal);
  identity resolution (strong-ID + weak fallback + conflicts);
  reconcile (10 verdict classes); runtime topology (OTel/Hubble/
  EndpointSlice); federation; drift journal; incident V3 (factorized,
  causal-gated); remediation planning (approval envelope, no apply);
  dynamic capability.
- **MCP**: 28 tools incl. `platformforge_live`; bounded output →
  redacted artifact refs; read-only annotations.
- **CLI**: `live <12 verbs>`; `observe`, `finops`, `product`, `sdd`,
  `lab`, `evals`, `graph`, `judge`, `policy`, `change`, `agents`,
  `forge`, `mcp`, `capability`, `store`, `bench`.
- **Contracts**: 14 JSON Schemas incl. observation, graph-v2,
  drift-event, change-event, collector-receipt.
- **Rules**: 63 catalog rules; `judge`/`policy check`.
- **Economy**: TokenSave packs, RTK, Caveman, budget routing; bench:
  `live_drift_2k` 3.9ms, `graph_build` 0.6ms, `index_time` 210ms.
- **SDD**: native lifecycle DISCOVER→LEARN with hash cascade; CYCLE-3
  shipped through it.

## Cycle 3 gaps (honest, carried forward)

- k8s `watch` deferred — snapshot + incremental cursors only.
- AWS collection covers core service set, not full catalog.
- Runtime edges limited to exported telemetry.
- No execution/mutation path at all — Cycle 4 adds the governed one.
- Remediation stops at plan + approval envelope (no policy engine,
  state machine, verification, or rollback chain).

## Cycle 4 build order (spec §294)

B models → C risk → D policy V2 → E approval → F state machine/ledger
→ G execution envelope → H git executor → I terraform → J gitops →
K verification → L rollback → M narrow k8s → N auto-remediation →
O runbooks → P golden path → Q finops/security gates → R operational
graph → S cross-forge → T lab V4 → U evals → V hardening → W reports.

Phase gate (§295): no executor before intent+risk+policy+approval+
ledger+preconditions. Executor gate (§296): dry-run + idempotency +
approval + failure tests. Auto-remediation gate (§297): verification +
rollback + policy + lab evidence. Production gate (§298): never
auto-enabled.
