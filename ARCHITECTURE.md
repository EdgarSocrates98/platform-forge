# ARCHITECTURE — Platform Forge

An **Agentic Platform Engineering Intelligence Platform**: offline-first,
deterministic-first, evidence-first, graph-aware, provider-neutral in the core.

## Epistemic pipeline (the contract everything honors)

```text
ARTIFACT → EXTRACT → FACTS → CORRELATE → GRAPH → RULES → FINDINGS
        → COMPOSITION → RECOMMENDATION / PLAN / REFUSAL
```

Never `artifact → LLM guess → recommendation`. LLMs (when present, as adapters)
compose, investigate and explain — they never replace observable facts.

## Truth model (evidence tiers)

```text
T0 measured runtime evidence   T4 official documentation
T1 provider/API observed state T5 declared operator context
T2 generated plan/state        T6 LLM inference
T3 repository configuration    T7 conjecture
```

T6/T7 can never silently become facts. Every recommendation states what is
observed / declared / inferred / unknown.

## Layered structure

```text
adapters (CLI · MCP · hosts · A2A)     — thin I/O, no logic
─────────────────────────────────────────────────────────
capabilities   — registry, contracts, parity
agentic        — coordinators, specialists, reviewers, referee, routing
engines        — sdd · graph · judge · rules · economy · risk · incidents
domains        — iac · kubernetes · gitops · cicd · observability · sre
                 finops · security · platform_product · cloud/{aws,azure,gcp}
kernel         — tokensave · rtk · caveman · context · ledger
core           — models(fact/finding/refusal) · provenance · hashing ·
                 artifact store · receipts · source registry · redaction
```

Rules: adapters → capabilities/agentic → engines → domains → kernel → core.
Nothing below calls anything above. Domains never import adapters or LLM SDKs.

## Deterministic core guarantees

- Python ≥3.10 stdlib + PyYAML + jsonschema + python-hcl2 only.
- Works fully offline: no cluster, cloud credential, MCP host, or LLM needed.
- Every artifact is content-addressed (sha256); cache keys are hashes, never
  filenames.
- Every important operation emits a receipt (`operation`, `inputs`, `hashes`,
  `facts`, `findings`, timings) enabling replay.

## Control-plane concept

Platform Forge models `desired ↕ diff ↕ observed` for Terraform/OpenTofu,
Kubernetes, Helm/Kustomize, GitOps, cloud resources, CI/CD, policies, SLOs, cost
controls and security posture. It understands, it does not mutate: mutation paths
are `inspect → propose → sandbox → verify → approve → apply`, all gated.

## Packaging

```bash
platformforge <verb> [--json] [--output F] [--detail-level summary|normal|full]
                     [--offline] [--strict]
```

`platformforge` is the CLI name; core lives in `platformforge/` (flat layout —
matches spark-forge convention, simpler than src layout for a tool users run
in-place). `platformforge-mcp` is an optional extra (`pip install platformforge[mcp]`).

## Boundaries

- vs **api-forge**: API Forge designs the service; Platform Forge owns where/how
  it runs, is deployed, governed, observed, costed. Hand-off contract carries
  runtime, port, health endpoint, SLO, resource profile, secrets refs,
  dependencies, deployment model.
- vs **spark-forge-aws**: Spark Forge owns data-workload internals; Platform
  Forge owns the EKS/EMR/runtime/network/IAM/cost envelope.
- vs **The Forge** (future orchestrator): Platform Forge answers
  `What capabilities do you have?` with a manifest — no hard coupling.

## Repository layout

```text
platformforge/
  models/      Fact, Finding, Refusal, evidence tiers (T0–T7)
  core/        redaction, receipts, artifact store, hashing, ownership,
               contradictions, workspace
  tokensave/   content-addressed index + bounded context packs
  rtk/         compact command output   caveman/   lossless compression
  economy/     ledger, strategies, quality-per-token
  routing/     adaptive cheap→premium routing
  graph/       Graphfy — nodes/edges+provenance, snapshots, diff, query,
               delivery + cross-repo edges
  rules/       engine + catalog/*.yaml (63 sourced rules)
  iac/ k8s/ gitops cicd/ observe/ finops/ security/ product/ cloud/
               domain analyzers → Facts
  collect/     dump sniffer → facts   diagnose/   per-node composition
  plan/        remediation v2 DAG     risk/       change-risk v2
  sandbox/     change review (copy-tree → apply → compare)
  sdd/         spec lifecycle + hash cascade
  agents/      roster, routing, referee v2, host mirrors
  mcp/         registry v2 + bounded/redacted tool surface
  forge/       capability manifest + interop   lab/   scenario runner
  evals/       corpus + coverage + precision   bench.py  measured benchmarks
  cli/         41 verbs — thin dispatch over the above
```

Sibling forges consulted during design: `api-forge`, `spark-forge-aws`
(contracts and conventions, not runtime dependencies).
