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
| `platform.change.*` | 5+ | core | yes | `change propose/sandbox/verify` | copy-tree → apply → analyze → compare; `approve/apply` refuse in core (host boundary) |
| `platform.drift` | 5+ | iac | yes | `analyze drift` | desired↔observed (tfstate) |
| `platform.risk` | — | core | yes | `risk` | §130 decomposition; criticality declared-only (§131) |
| `platform.sdd.*` | 3 | sdd | yes | `sdd init/artifact/status/gate/override` | lifecycle + hash cascade |
| `platform.economy.*` | 2 | economy | yes | `economy`, `tokens`, `rtk`, `caveman`, `route` | measured bytes/tokens |
| `platform.security.*` | 10 | security | yes | `analyze secrets/iam/sbom/supply` | secrets scan, IAM graph, SLSA |
| `platform.reliability.*` | 8 | sre | yes | `observe slo/otel/incident/capacity` | SLO, budget, capacity |
| `platform.finops.*` | 9 | finops | yes | `finops costs/allocate/focus/graph` | allocation, FOCUS, graph costing |
| `platform.lab.*` | 14 | lab | yes | `lab list/run/run-all` | 13 scenarios (L0 static tier) |
| `platform.product.*` | 11 | product | yes | `product maturity/scorecard/backstage` | CNCF maturity, Backstage projection |
| `platform.integrate/detach` | 13 | adapters | yes | `mcp integrate/detach` | host parity files |
| `platform.capability.*` | 13 | core | yes | `capability list/describe/manifest` | this registry |
| `platform.forge.*` | 15 | integrations | yes | `forge manifest/delegate/verify/discover/collect` | A2A envelope + sibling-forge ingress |

### Known gaps (declared, not hidden)

- `platform.collect` — generic ingress adapters (k8s export, cloud dumps)
  are not implemented; domain analyzers read artifacts directly instead.
- `platform.plan` as a standalone verb — covered by `analyze plan` +
  `change verify`.
- Lab tiers L1–L4 (containers/kind/cloud) and chaos (§93) — L0 static
  only; higher tiers need a host runtime the offline core doesn't assume.
- Eval framework (§94) — covered by `tests/` (unit/contract/golden via
  lab) rather than a separate evals runtime.

`platform.*` is a namespace, not a runtime requirement: every entry is
implemented locally, offline-capable unless marked otherwise.
