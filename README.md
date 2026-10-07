# Platform Forge

**Agentic Platform Engineering intelligence platform** — deterministic,
offline-first, evidence-first, graph-aware, provider-neutral in the core.

Platform Forge reads repositories, Terraform/OpenTofu, Kubernetes, GitOps,
CI/CD, observability data, SLOs, security posture, cost and ownership — and
builds one coherent, evidence-backed model of a platform. Facts have
provenance; findings cite evidence; unanswered questions come back as
named refusals, never hedged prose.

*Versão em Português: [README.pt-BR.md](README.pt-BR.md)*

## Install

```bash
pip install -e .            # core — offline-capable
pip install -e ".[dev]"     # + tests/lint
# or: uv sync && uv pip install -e .
```

## Quick start

```bash
platformforge doctor                       # environment health
platformforge init --repo .                # scaffold .platformforge/
platformforge inspect --repo .             # inventory analyzable artifacts
platformforge analyze iac ./infra          # HCL → facts
platformforge analyze k8s ./manifests      # manifests → facts
platformforge analyze gha --repo .         # workflows → facts
platformforge analyze kyverno ./policies   # kyverno/gatekeeper → facts (version-aware)
platformforge analyze cosign bundle.json   # sigstore shape — claimed ≠ verified
platformforge analyze slsa prov.json       # SLSA requirement/evidence/gap
platformforge analyze cloud-aws ./dumps    # AWS CLI dumps → T1 facts
platformforge judge facts.json             # rules → findings
platformforge judge facts.json --versions '{"kubernetes":"1.29"}'  # version-gated rules
platformforge graph build facts.json       # facts → provenanced graph
platformforge graph blast --node X         # blast radius (per impact class)
platformforge graph identity-become --node role/x   # who can become this role
platformforge observe slo contract.yaml --sli '{"total_events":1e6,"bad_events":400}'
platformforge observe postmortem --incident i.json # unresolved root cause stays named
platformforge finops costs billing.json    # cost facts + summary
platformforge finops ingest cur.csv        # CUR/Azure/GCP/OpenCost/Kubecost → rows
platformforge finops focus-validate rows.json # FOCUS 1.0 column compliance
platformforge finops unit costs.json --denominators d.json # cost/request etc.
platformforge change review --repo . --patch diff.patch   # sandbox → graph delta → risk
platformforge product maturity --signals s.json
platformforge mcp tools                    # bounded MCP capability surface
platformforge mcp serve                    # stdio server (same core as CLI)
platformforge lab run-all                  # Forge Lab scenario suite
platformforge lab chaos lab/chaos-pod-kill # fault injection on the graph
platformforge evals run                    # eval framework (§94–95)
platformforge evals coverage               # rule ↔ case coverage matrix
platformforge evals precision              # measured false-positive rate
platformforge store gc                     # §151 — dry-run GC of stale blobs
platformforge collect ./dumps              # sniff dumps → facts
platformforge diagnose <node> --findings j.json --facts f.json
platformforge plan findings.json           # ordered remediation plan
platformforge policy check facts.json      # catalog as policy
platformforge security ./dumps             # secrets+iam+sbom+supply bundle
platformforge sdd status --feature F       # spec lifecycle + hash cascade
platformforge forge manifest               # capability manifest (interop)
```

## Pipeline

```
artifacts → analyze → facts ──► judge → findings ──► scorecards / gates
               │                                   ▲ rules/catalog/
               └──────► graph build → graphfy ──────┘ (deps, blast, diff)
```

Facts carry evidence tiers (measured → provider → plan → repo → doc →
declared → inferred). Graph edges inherit provenance. Every mutation path
goes through `inspect → propose → sandbox → verify → approve → apply`;
the core itself never mutates anything.

## Design docs

[ARCHITECTURE.md](ARCHITECTURE.md) · [GRAPHFY.md](GRAPHFY.md) ·
[ECONOMY.md](ECONOMY.md) · [SDD.md](SDD.md) · [AGENTIC-OS.md](AGENTIC-OS.md) ·
[DOMAIN-MAP.md](DOMAIN-MAP.md) · [CAPABILITIES.md](CAPABILITIES.md) ·
[RESEARCH.md](RESEARCH.md) · [ROADMAP.md](ROADMAP.md) ·
[KNOWLEDGE.md](KNOWLEDGE.md) · [RULES.md](RULES.md) ·
[SECURITY.md](SECURITY.md) · [EVALS.md](EVALS.md) · [CLOUD.md](CLOUD.md) ·
[GOLDEN-PATHS.md](GOLDEN-PATHS.md) · [QUALITY-PER-TOKEN.md](QUALITY-PER-TOKEN.md)

## License

MIT — see [LICENSE](LICENSE), [SOURCES.md](SOURCES.md), [CREDITS.md](CREDITS.md).
