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
unknown) · `paths` · `gaps` · `cycles` · `diff` (semantic categories,
every change cites `fact_ids`) · `snapshots` · `stats` ·
`identity-become|identity-access|identity-workloads|identity-blast`
(§100–101: no-path-found is a named result, never "no risk").

Provenance on every edge: `observed | planned | declared | inferred`.
Node `state`: observed > planned > desired > inferred.

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
