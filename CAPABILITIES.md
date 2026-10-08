# CAPABILITIES — Platform Forge capability matrix

Machine-readable source of truth: `platformforge/mcp/registry.py`
(`CAPABILITIES`). CLI verbs and MCP tools are projections of this registry —
`platformforge capability list|describe|manifest` and the MCP adapter read
the same data. Parity is tested, not assumed (`tests/test_mcp.py`).

Each capability declares:

```yaml
id: platform.k8s.analyze
version: "1"
inputs: [k8s-manifests]
outputs: [facts, findings]
risk: read-only            # read-only | propose | mutating
required_evidence: [t3-repo-config]
offline: true
mutable: false
cost_class: deterministic  # deterministic | indexed | local-model | provider-model
agent_requirements: []     # specialists this capability can dispatch to
```

## Matrix

| Capability ID | Phase | Domain | Offline | CLI verb | Notes |
|---|---|---|---|---|---|
| `platform.inspect` | 1 | core | yes | `inspect` | inventory artifacts; workspace-aware (§126) |
| `platform.init` | 1 | core | yes | `init` | scaffold `.platformforge/` + `workspace.yaml` |
| `platform.status` | 1 | core | yes | `status` | workspace + store status |
| `platform.doctor` | 1 | core | yes | `doctor` | environment health-check |
| `platform.analyze` | 5+ | * | yes | `analyze <dom>` | extract facts; fans out over workspace members |
| `platform.graph.*` | 4 | graph | yes | `graph build/deps/dependents/blast/paths/gaps/cycles/diff` | facts→provenanced graph |
| `platform.judge` | 1 | core | yes | `judge` | rule catalog over facts |
| `platform.diagnose` | 8 | sre | yes | `observe incident` | correlate alerts+changes+graph (never cause-as-certainty) |
| `platform.explain` | 2 | core | yes | `explain` | evidence chain for a finding |
| `platform.recommend` | 11 | * | yes | `recommend` | findings→Recommendation objects; no-evidence → refused |
| `platform.change.*` | 5+ | core | yes | `change propose/sandbox/verify/review` | copy-tree → apply → analyze → compare + semantic graph delta + findings delta + risk; `approve/apply` refuse in core (host boundary) |
| `platform.drift` | 5+ | iac | yes | `analyze drift` | desired↔observed (tfstate) |
| `platform.risk` | — | core | yes | `risk` | §130 decomposition; criticality declared-only (§131) |
| `platform.sdd.*` | 3 | sdd | yes | `sdd init/artifact/status/gate/override` | lifecycle + hash cascade |
| `platform.economy.*` | 2 | economy | yes | `economy`, `tokens`, `rtk`, `caveman`, `route` | measured bytes/tokens |
| `platform.security.*` | 10 | security | yes | `analyze secrets/iam/sbom/supply/kyverno/cosign/slsa` | secrets scan, IAM v2 (trust/SCP/boundary/OIDC/role chaining), Kyverno version-aware, SLSA requirement/evidence/gap, Cosign shape (claimed ≠ verified) |
| `platform.identity.*` | 4 | security | yes | `graph identity-become/access/workloads/blast` | §100–101 identity paths; no-path-found is named, never "no risk" |
| `platform.reliability.*` | 8 | sre | yes | `observe slo/slo-burn/otel/semconv/incident/timeline/postmortem/capacity/dr/prometheus/grafana` | SLO multi-window burn, incident/postmortem, DR, prom/grafana, OTel semconv |
| `platform.finops.*` | 9 | finops | yes | `finops costs/allocate/focus/focus-validate/unit/ingest/report/graph` | allocation, FOCUS 1.0 validation, unit economics, CUR/Azure/GCP/OpenCost/Kubecost ingest, idle/rightsizing/anomaly/forecast/commitments/shared |
| `platform.lab.*` | 14 | lab | yes | `lab list/run/run-all` | 13 scenarios; §118 profiles static/container/kubernetes/cloud — non-static refused without `--allow-profile` + §119 safety contract |
| `platform.product.*` | 11 | product | yes | `product maturity/scorecard/backstage` | CNCF maturity, Backstage projection |
| `platform.integrate/detach` | 13 | adapters | yes | `mcp integrate/detach` | host parity files |
| `platform.capability.*` | 13 | core | yes | `capability list/describe/manifest/check` | §112 v2 contracts + §139 negotiation (domain+version) |
| `platform.forge.*` | 15 | integrations | yes | `forge manifest/delegate/verify/discover/collect` | A2A envelope + sibling-forge ingress |
| `platform.collect` | 1+ | core | yes | `collect <path>` | shape-sniff dumps (k8s/plan/state/iam/sbom/supply/finops) → facts; undetected files reported, never dropped; secrets baseline always runs |
| `platform.plan` | 8+ | core | yes | `plan <findings.json>` | ordered remediation plan (severity→blast), no-evidence steps refused |
| `platform.correlate` | 8 | sre | yes | `correlate <otel.yaml>` | = `observe otel` |
| `platform.diff` | 4 | graph | yes | `diff --before f1.json --after f2.json` | facts docs → graphs → diff |
| `platform.impact` | 4 | graph | yes | `impact --node` | = `graph blast` |
| `platform.context` | 2 | economy | yes | `context --task --input-budget` | = `tokens pack` |
| `platform.policy` | 1 | core | yes | `policy check/list` | rule catalog as policy layer |
| `platform.security` | 10 | security | yes | `security <root>` | secrets+iam+sbom+supply bundle → security-domain judge |
| `platform.reliability` | 8 | sre | yes | `reliability <facts.json>` | sre+k8s rules only |
| `platform.integrate` | 13 | adapters | yes | `integrate --host` | = `mcp integrate/detach` |
| `platform.evals` | 14 | lab | yes | `evals run/list/coverage/precision` | §94 types + §95 variants; 63/63 rule coverage (evals + lab); §127 measured precision |
| `platform.lab.chaos` | 14 | lab | yes | `lab chaos <dir>` | §93 fault injection on the graph (simulation); prod targets refused unless `--allow-prod` |
| `platform.knowledge` | 2 | economy | yes | `knowledge` | source registry freshness check — stale/unresolved/conflicted flagged |
| `platform.agents` | 12 | agents | yes | `agents list/lint/sync/check/playbook/referee/bench` | canonical 41-agent roster (AgentSpec v2), mirror sync + drift check, zero-subagent playbook, bounded debate, strategy bench |
| `platform.store` | 2 | core | yes | `store stats/gc` | §151 — content-addressed store; gc dry-run by default, never deletes referenced artifacts, `--execute` to delete |
| `platform.bench` | 16 | core | yes | `bench run/tokens/scale` | §148–150 — measured perf/token/storage on eval fixtures; `scale` measures graph+store to 10k nodes / 500k edges; `unsupported-on-host` when a size can't be attempted |
| `platform.ownership` | 4 | core | yes | `analyze ownership/contradictions` | §116/§136–137 — CODEOWNERS/Backstage/workspace/k8s-labels/cloud-tags signals; `ownership.conflicted` + `state.contradiction` facts |
| `platform.fleet` | 13 | fleet | yes | `fleet <verb>` | Cycle 5 — Fleet/FleetMember/FleetSnapshot (coverage first-class), org-graph layers, 9 fleet questions, FinOps V4, capacity, history, golden-path, policy intel — fleet-dir inputs, coverage always reported |
| `platform.analytics` | 3 | analytics | yes | `analytics summary|metric|maturity` | deterministic aggregates only; per-dimension maturity — unknown ≠ 0, no opaque scores, no fake ML |
| `platform.optimize` | 5 | optimize | yes | `optimize scan|list|portfolio|explain|plan` | opportunity → recommendation (uncertainty/suppression honest) → `plan` emits ChangeIntent only — never executes (§303) |
| `platform.ai` | 3 | aiplat | yes | `ai workloads|gpu|economics` | GPU/accelerator detection, pool risk, unit economics — denominators required, missing → `unknown` |
| `platform.federation` | 3 | federation | opt-in | `federation manifest|export|query` | bounded intelligence exchange; classification policy fail-closed; secrets always denied; no authority crosses (feature flag, default off) |

| `platform.live` | 12 | live | host-side | `live <verb>` | observation envelopes + store + budgets; kubectl/aws collectors (read-only allowlist, credential-flag refusal); identity resolution; desired↔planned↔observed↔runtime reconcile; runtime topology (OTel/Hubble/EndpointSlice); cluster federation; drift journal; incident V3 (factorized ranking, correlation≠causation); remediation planning (never applies); dynamic `live capability` — see LIVE.md |
| `platform.ops` | 11 | ops | governed | `ops <verb>` | governed control plane (Cycle 4 + 4.1): ChangeIntent → ChangePlan DAG → simulation S0–S5 → risk R0–R5 → policy V2 → hash-bound approval → typed-action envelope → precondition gates → FSM + append-only ledger → verify → converge/rollback → audit. `ops run` dry-runs by default; `--execute` uses host argv transports only; forbidden actions (`shell.run`, …) → `PF-OPS-UNSTRUCTURED`; material-bound rollback v2 (ROLLBACK.md), ExpectedDelta gate, integrity-seal approvals; cross-Forge delegation never carries execution authority — see OPS.md |

### Known gaps (declared, not hidden)

- Lab tiers L1–L4 (containers/kind/cloud) — L0 static + graph-simulated
  chaos only; higher tiers need a host runtime the offline core doesn't
  assume (live-kind lab exists, gated by `--profile kubernetes`).
- `collect` covers the offline dump shapes listed above; live-provider
  collection uses `live snapshot` (host-side transports, read-only).

`platform.*` is a namespace, not a runtime requirement: every entry is
implemented locally, offline-capable unless marked otherwise.
