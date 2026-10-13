# CYCLE 3 — FINAL REPORT

Runtime & Live Platform Intelligence — `prompt_evo_cycle3.md`.
Scope: phases 0/A–M executed sequentially; each phase committed;
gates green at every commit. Cycle 4 deliberately not started (§291).

**Verdict:** Platform Forge now answers "what is actually happening on
this platform?" across desired / planned / observed / runtime — with
coverage, freshness, identity, and evidence made explicit. The core
stays offline, deterministic, SDK-free and read-only; all provider IO
is a host-side transport boundary.

- Tests: **411 pass** (baseline 260 → +151)
- Evals: **48 pass** (baseline 39 → +9 live cases)
- Lab: **17 pass** (live-kind gated to `--profile kubernetes`)
- New surface: `platformforge live <12 verbs>`; `platformforge_live` MCP
  capability; graph v2 (temporal + multi-layer evidence)
- Live/graph code: ~4.8k LOC core + transport wrappers + fixtures

Commits: `aa5f772` baseline → `67c4fca` A → `9ab239c` B → `04a5848` C →
`24a8f93` D → `4501e1f` E → `0a4824b` F → `7e5f5aa` G → `aa6d733` H →
`c400d8f` I → `1a90cbd` J → `f217477` K → `f7f5bd3` L → `8291012` M.

---

## §275 — Capability matrix

| Capability | Before | After | Implementation | Tests | Evals | Evidence | Known gaps |
|---|---|---|---|---|---|---|---|
| Observation model | none — dumps only | typed envelope + append-only store + cursors + receipts | `live/{models,store,envelope,budget,cursors}.py` + `contracts/observation.schema.json` | unit suite | live-* | `observation_id`, coverage, ledger | watch/stream not implemented (snapshot+incremental only) |
| Kubernetes live | none | read-only kubectl collector: discovery, pagination, 410-refetch, secret-safe | `live/collectors/{k8s,k8s_transport}.py` | `test_live_k8s.py`, security props | live-k8s-collect, live-secrets-boundary | envelope + denied-call coverage | needs host kubectl+context; watch deferred |
| AWS live | none | read-only aws CLI collector: preflight, per-service probes, region scoping | `live/collectors/{aws,aws_transport}.py` | `test_live_aws.py` | live-aws-collect | STS account + denied-call evidence | service catalog covers core set, not every AWS service |
| Identity | none | strong-ID-first + weak fallback + explicit conflicts + cross-provider rules | `live/identity.py` | `test_live_identity.py` | live-reconcile | `identity.conflict`/`correlated` | cloud↔k8s workload identity needs annotation/role evidence |
| Reconciliation | declared↔plan drift only | desired↔planned↔observed↔runtime, 10 verdict classes, freshness-aware | `live/reconcile.py` | suite + CLI | live-reconcile | per-resource verdicts + refs | defaulted fields need allowlisting; eventual-consistency window is config, not measured |
| Graph | v1 snapshots | v2: multi-layer edge evidence, temporal fields, event ledger, expiry | `graph/{model,temporal,events,migrate}.py` | graph tests | live-temporal-graph | `Edge.evidence`, `temporal.*` | expiry mark-only (no auto-prune — by design) |
| Runtime topology | hubble/otel analyzers (facts) | runtime edges with behavior classes + graph layering | `live/topology.py` | suite | — | `observed`/`observed-undeclared` edges | telemetry coverage is what the sources export — gaps reported, not inferred |
| Multi-cluster | none | cluster registry + federated reconcile view | `live/federation.py` | suite | live-multicluster | per-scope + `federated` verdicts | federation = union of per-cluster scopes; no cross-cluster causality |
| Live drift | `analyze drift` (static dumps) | observation↔observation diff → dedup journal → DriftEvents | `live/drift.py` | `test_live_drift.py` | live-drift | `deletion_evidence`, journal | noise control = fingerprint dedup (tunable) |
| Incident intel | v2 correlation | canonical timeline + factorized ranking + postmortem V3 | `live/incident.py` | `test_live_incident.py` | live-incident | per-factor score breakdown | `confirmed` unreachable without `evidence.causal` — by design |
| Remediation | `change` review (dry) | plan + simulation + projected graph + approval envelope | `live/remediate.py` | `test_live_remediate.py` | live-plan | deterministic plan hash | no apply — intentional |
| Economy | token budgets | provider-call budgets + ledger + incremental cursors | `live/budget.py` + transports | budget tests | — | per-call `{op,ms,bytes}` | savings claim = measured delta only |
| MCP/Forge | 27 tools | `platformforge_live` capability: same handlers, bounded, redacted artifacts | `mcp/{registry,tools}.py`, `live/capability.py` | `test_live_capability.py` | — | capability metadata + artifact refs | MCP output truncated→artifact ref at bound |

## §276 — Observation report

- **Collectors**: `kubernetes` (kubectl get/api-resources) and `aws`
  (aws CLI describe/list/get + STS preflight). Both transport-injected;
  fixtures replay the same path offline.
- **Resource coverage**: declared in `scope` (namespaces, resource
  types, regions, services); `coverage` records attempted/succeeded/
  denied/timed_out — `complete` only when all attempted succeeded.
- **Permission behavior**: denied calls never abort the envelope; they
  land in `denial_details` with the operation and reason, and
  reconciliation treats affected scope as `unresolved`, not empty.
- **Freshness**: `collected_at` per envelope; consumers pass a window;
  expired input → `stale-observation` verdict / `temporal.expired`
  edges.
- **Absence semantics**: "not enumerated" ≠ "deleted" unless coverage
  is complete; removals carry `deletion_evidence` (previous envelope
  id + last_seen).

## §277 — Graph report

- Snapshot counts unchanged in semantics (v1 loads byte-identical);
  v2 adds `temporal` + `evidence` layers — upgrade on write via
  `migrate.py`, so `graph_hash` of historical snapshots is stable.
- Temporal capabilities: `edges_between`, `expire_stale_edges`
  (marks `temporal.expired`, never deletes), per-edge
  `first_seen/last_seen/sample_count`.
- Layer evidence: an edge accumulated from declared+observed keeps
  both provenance records — `layers()` exposes all contributors.
- Bench (measured, this workspace): `graph_build` 0.6ms median on eval
  fixtures; `live_drift_2k` 3.9ms for 2k-resource diff; `context_build`
  28.5ms; `index_time` 210ms/53 files.

## §278 — Economy report (measured only)

| Metric | Value | Source |
|---|---|---|
| k8s collect (fixture, 4 resource types) | 4 API calls, recorded per-call in ledger | live-k8s-collect envelope |
| aws collect (fixture, 2 services + STS) | 3 calls | live-aws-collect envelope |
| envelope→envelope diff, 2k resources | 3.9ms median | `bench.live_drift_2k` |
| incremental collection | resumes via cursor — delta fetch, not full relist | `live/cursors.py` |
| MCP bounded output | oversized payloads persisted as redacted artifact refs | `mcp/tools.py` |

No "saves N%" claims — only deltas the ledger measures.

## §279 — Security report

- **Credential handling**: transports refuse credential flags and
  mutating verbs before subprocess; registry stores context/role
  references, never secrets; `--offline` blocks transports entirely.
- **Secret leakage**: property tests plant secret payloads +
  `auth.token`-class annotations and scan serialized envelopes,
  graph output, MCP artifacts — zero survivors (one real bug found and
  fixed: anchored regex let `auth.token` through; now substring).
- **Mutation checks**: no `apply` verb; `live plan --strict` exits 2 on
  mutating actions; transport allowlists tested with forbidden calls.
- **RBAC/IAM minimum**: `live rbac` / `live required-permissions`
  emit the least-privilege manifests; doctor probes verify.

## §280 — Honest gaps

- AWS collection covers a core service set; an **unsupported service**
  is reported in coverage, not silently skipped — but it is not
  collected either.
- **Permission gaps** are first-class output — a denied `iam:ListUsers`
  shows in `denial_details`; we report the gap, we don't fill it.
- **Sampling**: Hubble/OTel runtime edges reflect exported telemetry —
  if the mesh doesn't export it, the edge doesn't exist; `runtime`
  coverage is source-limited.
- **Stale snapshots**: usable but downgraded — never presented as
  current.
- **Unknown identity**: ambiguous weak matches surface as
  `identity.conflict` — no silent merge.
- k8s `watch` (streaming) deferred — snapshot + incremental cursors
  cover the Cycle-3 contract; watch is Cycle-4 candidate work.
- Eventual-consistency window is a `--window` knob, not a learned value.

## §281 — Maturity (honest scores)

Core 9.8 · Evidence 9.8 · Graphfy 9.7 · SDD 9.0 · TokenSave 9.2 ·
Economy 9.1 · Knowledge 8.8 · IaC 8.7 · K8s static 9.2 ·
**K8s live 8.5** (snapshot+incremental; watch missing) ·
AWS static 8.4 · **AWS live 8.3** (core services only) ·
**Runtime topology 8.0** (3 sources; coverage source-limited) ·
**Reconciliation 9.0** · **Incident 8.5** (ranking explainable;
causal gate strict) · Platform product 9.0 · MCP 9.2 · Forge interop 9.2.

## §284–290 — Adversarial review

**Observation**: missing data cannot masquerade as absence — denied/
partial scopes yield `unresolved`/coverage flags, and drift events for
removals require `deletion_evidence`. Stale data cannot look current —
`stale-observation` and `temporal.expired` are first-class verdicts.
Partial data cannot look complete — `coverage.complete` is computed,
not assumed.

**Security**: credentials never enter the core (host transports only;
flag injection refused; registry holds references). Secrets cannot be
persisted — value-stripping is a boundary property, property-tested
end-to-end. Collectors cannot mutate — verb allowlists + `--offline`.
Telemetry is whitelisted to controlled projections, so sensitive
payloads cannot ride through spans/flows.

**Graph**: declared evidence survives observed writes — layers union.
Temporal history is mark-not-delete. Cross-cluster/account identity
collisions are scoped by cluster/account and surface as conflicts.

**Economy**: collection is scoped and budgeted; metadata-first
(ids/digests before bodies) is the default shape; provider-call savings
are measured in the ledger — no unmeasured claims.

**Incident**: causality is gated on `evidence.causal`; ranking is a
named-factor weighted sum — every score decomposes. Unresolved root
cause stays unresolved.

**Reconciliation**: defaulted/computed fields don't fake drift —
comparison is restricted to shared comparable attributes, and
`drift.allowlist` marks accepted divergence. Controller-created orphans
are classed `observed-orphan` (not errors), and the eventual-consistency
window suppresses flagging resources observed mid-propagation.

## §292 — Documented only, not implemented

Cycle 4 candidate: Controlled Platform Operations — approved execution,
progressive remediation, policy-gated mutations, rollback verification.
`live plan` deliberately stops at the approval envelope.

## North star (§293)

Declared (repo scan) → planned (tfplan) → observed (live envelopes w/
freshness+coverage) → runtime (topology edges) → drift journal →
incident candidates → remediation plan + projected graph + blast
radius + validation checklist. Every sentence cites evidence; every
gap says `unresolved`. That is what shipped.
