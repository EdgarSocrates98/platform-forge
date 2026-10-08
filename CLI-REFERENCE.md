# CLI REFERENCE — `platformforge`

Every verb below is real and tested; the docs-drift test
(`tests/test_docs_drift.py`) fails if a verb exists without docs or a
doc claims a verb that does not exist.

Global flags on every verb: `--json` · `--output <file>` ·
`--detail-level summary|normal|full` (real bounding) · `--offline` ·
`--strict` (warnings become failures where supported).

## Discovery & inventory

| Verb | What it does |
|---|---|
| `doctor [--deep]` | Environment health. `--deep` adds workspace/config, capability manifest, knowledge freshness, host parity, index + artifact-store checks. |
| `init --repo <dir>` | Scaffold `.platformforge/` + `workspace.yaml` (multi-repo members with roles). |
| `status` | Workspace + store status. |
| `inspect [--repo]` | Inventory analyzable artifacts across workspace members. |
| `collect <path>` | Shape-sniff dumps (k8s/plan/state/iam/sbom/supply/finops/cloud) → facts. Undetected files are *reported*, never dropped; secrets baseline always runs. |

## Extraction — `analyze <domain> <path>`

All analyzers are offline, dump-only, and emit tiered `Fact`s.

`iac` · `plan` (tfplan) · `state` (tfstate) · `drift` (desired↔observed) ·
`k8s` · `helm` · `kustomize` · `gitops` (ArgoCD/Flux depth) · `gha` ·
`iam` · `sbom` · `secrets` · `supply` · `kyverno` (version-aware) ·
`cosign` · `slsa` · `hubble` (Cilium flows, T0/T1) · `catalog` ·
`crossplane` · `cloud-aws` · `cloud-azure` · `cloud-gcp` ·
`ownership` (CODEOWNERS/Backstage/workspace/k8s/cloud-tag signals →
`ownership.conflicted`) · `contradictions` (declared-vs-observed →
`state.contradiction`).

## Judgment & policy

| Verb | What it does |
|---|---|
| `judge <facts.json> [--versions '{...}']` | Rule catalog → findings. `--versions` declares product versions for gated rules; unknown → `version_notes` unresolved, not a verdict. |
| `policy check <facts.json>` / `policy list` | The rule catalog as a policy layer. |
| `security <path>` | Bundle: secrets+iam+sbom+supply analysis → security-domain findings. |
| `reliability <facts.json>` | sre+k8s rules only. |

## Graph — `graph <verb>`

`build <facts.json>` · `deps` · `dependents` · `blast --node` (impact
classes: direct/transitive/runtime/security/reliability/cost/compliance/
unknown) · `paths` · `gaps` (incl. SPOF + unreachable analysis) ·
`cycles` · `diff` (semantic categories,
every change cites `fact_ids`) · `snapshots` · `stats` ·
`at --at <ts>` (graph as-of timestamp) · `timeline --edge-id|--node`
(temporal provenance) ·
`identity-become|identity-access|identity-workloads|identity-blast`
(§100–101: no-path-found is a named result, never "no risk").

Provenance on every edge: `observed | planned | declared | inferred`.
Node `state`: observed > planned > desired > inferred.
v2 adds multi-layer evidence + `temporal.{first_seen,last_seen,
expired}`; stale observed edges are *marked expired, never deleted*
(`graph/temporal.py`).

## Live — `live <verb>`

Host-side read-only collection + live intelligence. The core never does
network IO; transports (kubectl/aws CLI) are the boundary. Every
collector call is budgeted (`--max-objects/--max-api-calls/--max-bytes`)
and ledgered. Absence is never asserted on partial coverage. See
LIVE.md.

| Verb | What it does |
|---|---|
| `live snapshot` | Collect → observation envelope (`--provider kubernetes|aws`, scope flags, `--no-store`). |
| `live status` | Observation store status. |
| `live doctor [--deep]` | Provider preflight: binary, auth, per-resource permissions. |
| `live rbac` | Minimum ClusterRole (`--namespaced-only` → Role). |
| `live required-permissions` | Minimum AWS IAM actions + k8s RBAC. |
| `live reconcile` | desired↔planned↔observed↔runtime → drift classes; stale→`stale-observation`, partial coverage→`unresolved`. |
| `live topology` | `--otel|--hubble|--slices` → runtime edges; `--apply-to-graph` layers evidence. |
| `live clusters` | Cluster registry (`--register <json>`) + federation view. |
| `live drift` | Observation↔observation diff → deduplicated drift-event journal. |
| `live changes` | CloudTrail-style change-event journal: `--collect` (aws adapter, refuses `--offline`), `--events-file` (offline append), `--gc` (journal GC), bare read (`--since/--resource`). |
| `live incident` | Canonical timeline + factorized candidate ranking → postmortem V3 (`confirmed` needs causal evidence). |
| `live plan` | Drift events → safe remediation plan + approval envelope (hash-pinned). Never applies; `--strict` exits 2 on mutating actions. |
| `live capability` | Dynamic capability availability (host prereqs, budgets, provider access). |

## Operations — `ops <verb>` (Cycle 4)

Governed control plane: intent → plan → simulate → risk → policy →
hash-bound approval → typed-action execution → verify → converge/rollback
→ audit. Dry-run is the default; `--execute` wires host argv transports
(never shell strings) and still requires a valid approval bound to the
frozen envelope hash. Forbidden verbs (`shell.run`, `kubectl.exec`, …)
refuse `PF-OPS-UNSTRUCTURED`. See OPS.md.

| Verb | What it does |
|---|---|
| `ops capabilities` | Typed action catalog + autonomy ceiling (A4) + delegation contract. |
| `ops config` | Load `platformforge.yaml` ops config (schema v2) + violations. |
| `ops delegate --request f.json` | Validate a cross-Forge delegation request (never grants execution authority). |
| `ops intent --intent f.json` | Propose: intent → source-of-truth resolution + evidence check. |
| `ops plan --plan f.yaml` | Build + validate a ChangePlan DAG → plan hash. |
| `ops simulate --plan f.yaml --level S1` | Deterministic S0–S5 simulation receipt. |
| `ops risk --plan f.yaml --environment E` | R0–R5 risk decomposition per step. |
| `ops policy-eval --plan f.yaml --policies p.yaml` | Policy V2 decision (deny → exit 2). |
| `ops runbook [id\|list] [--bind p.json]` | Structured runbooks: list, show, bind params. |
| `ops run --spec ops.yaml [--execute]` | Full governed pipeline on a spec (intent/steps/policies/approvals/observation/verify). Persists to the operation store; emits the operational graph projection. |
| `ops approve` | Mint a hash-bound approval artifact (`--subject-hash/--actor/--approval-type/--expires-at/--bounds/--scope`). Never executes. |
| `ops status` / `ops history` | Stored operation state / append-only ledger entries (`--operation-id`, `history --resource`). |
| `ops rollback --operation-id [--execute]` | Execute the stored rollback plan (dry-run default). |
| `ops autorem-eval --plan f.yaml` | A5 auto-remediation eligibility gate. |
| `ops analytics` | LEARN: outcome/rollback/failure analytics over the store. |
| `ops graph [--operation-id]` | Operational Graphfy projection rebuilt from ledgers. |
| `ops store-list` / `ops store-verify --operation-id` | Append-only operation store + hash-chain audit. |

## Compose verbs

| Verb | What it does |
|---|---|
| `diagnose <node> --findings f.json --facts x.json` | Per-node facts+findings+blast+unresolved. |
| `plan <findings.json>` | `platformforge.remediation/v2` — severity/blast/reversibility ordering + dependency DAG; no-evidence findings refused; apply is host-side. |
| `correlate <otel.yaml>` | Trace↔log↔metric correlation (= `observe otel`). |
| `diff --before a.json --after b.json` | facts docs → graphs → semantic diff. |
| `drift` | desired vs observed state diff. |
| `impact --node X` | Blast radius (= `graph blast`). |
| `explain <finding-id>` | Evidence chain: fact→rule→source→version→unlock. |
| `recommend <findings.json>` | Structured recommendations: change/risks/validation/rollback/tradeoffs; quantified effects require a benchmark ref. |
| `risk` | §130 change-risk decomposition (blast, criticality, prod, identity, exposure, data, availability, cost, reversibility, coverage). |
| `change propose|sandbox|verify|review` | §85–86 sandboxed change review. `approve|apply` refuse — host boundary. |

## Observability / SRE — `observe <verb>`

`slo` · `slo-burn` (multi-window) · `otel` · `semconv` · `incident` ·
`timeline` · `postmortem` · `capacity` · `dr` · `prometheus` · `grafana`.

## FinOps — `finops <verb>`

`costs` · `allocate` · `focus` · `focus-validate` (FOCUS 1.0 columns) ·
`unit` · `ingest` (CUR/Azure/GCP/OpenCost/Kubecost → normalized rows) ·
`report` (idle/rightsizing/anomaly/forecast/commitments) · `graph`.

## Platform product — `product <verb>`

`maturity` (v2: observed vs declared, `overclaimed` flagged) ·
`scorecard` (9 axes, unknown ≠ 0) · `backstage` · `paths` · `path` ·
`capabilities` · `path-analyze`.

## Economy — `tokens|rtk|caveman|economy|route|context`

`tokens index|pack|search|stats|ledger|delta` · `rtk compact|expand` ·
`caveman <text>` (redact-first compression) ·
`economy report|strategy|compare|qpt` (quality-per-token measured) ·
`route` · `context --task --input-budget` (= `tokens pack`).

## SDD — `sdd <verb>`

`discover · define · contract · design · plan · build · verify · review ·
ship · init · artifact · status · check · stamp · learn` — lifecycle
artifacts + hash cascade gates.

## Lab & evals

| Verb | What it does |
|---|---|
| `lab list|run|run-all` | Forge Lab scenarios (fixture + `expected.yaml`). `--profile static|container|kubernetes|cloud`; non-static needs `--allow-profile` + safety contract. |
| `lab chaos <dir>` | Fault injection on the graph (`environment: simulation`). Production targets refused without `--allow-prod`. |
| `evals run|list|coverage|precision` | 34-case corpus; coverage = rule↔case map (63/63); precision measured on negative corpus. |

## Agents, capability & interop

| Verb | What it does |
|---|---|
| `agents list|lint|sync|playbook|referee` | Roster, host-mirror sync (`.claude/agents`, `.agents/agents`, `.codex/agents`), referee arbitration (6 axes). |
| `capability list|describe|manifest|check` | Registry v2 contracts; `check --domain k8s --version 1.29` negotiates support — unknown versions degrade to unresolved. |
| `forge manifest|discover|collect|delegate|verify` | Forge interop manifest + A2A envelope + sibling-forge ingress. |
| `mcp tools|serve|call|integrate|detach` | MCP server + host parity files. |
| `integrate --host <h>` | = `mcp integrate`. |

## Knowledge & store

| Verb | What it does |
|---|---|
| `knowledge` | Source registry freshness (stale/conflicted/unresolved flagged). |
| `store stats|gc` | Content-addressed artifact store; `gc` is dry-run by default, never deletes referenced blobs, `--execute` deletes. |
| `bench run|tokens` | Measured perf/token/storage on eval fixtures — `measured, not a claim`. |

## Refusals

Insufficient evidence never becomes a hedged sentence. It returns a
named refusal: `{refusal: <code>, unlock: <what would answer it>}`.
