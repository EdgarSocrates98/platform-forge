<p align="center">
  <img src="docs/assets/logo.png" alt="Platform Forge" width="420">
</p>

# Platform Forge
**Plataforma de inteligência em Platform Engineering** — determinística,
offline-first, evidence-first, grafo-ciente, neutra a provedor no núcleo.

O Platform Forge lê repositórios, Terraform/OpenTofu, Kubernetes, GitOps,
CI/CD, observabilidade, SLOs, postura de segurança, custo e ownership — e
constrói um modelo coerente, auditável e sustentado por evidência da
plataforma. Fatos têm proveniência; findings citam evidência; perguntas
sem resposta voltam como recusas nomeadas — nunca texto evasivo.

*English version: [README.md](README.md)*

## Instalação

```bash
pip install -e .            # núcleo — funciona offline
pip install -e ".[dev]"     # + testes/lint
# ou: uv sync && uv pip install -e .
```

## Início rápido

```bash
platformforge doctor [--deep]              # saúde do ambiente (+ deep: manifest, knowledge, index, store)
platformforge init --repo .                # scaffolding .platformforge/ + workspace.yaml
platformforge inspect --repo .             # inventário de artefatos
platformforge collect ./dumps              # sniff de dumps → fatos
platformforge analyze iac ./infra          # HCL → fatos
platformforge analyze k8s ./manifests      # manifests → fatos
platformforge analyze gha --repo .         # workflows → fatos
platformforge analyze kyverno ./policies   # kyverno/gatekeeper → fatos (version-aware)
platformforge analyze cosign bundle.json   # sigstore shape — claimed ≠ verified
platformforge analyze slsa prov.json       # SLSA requirement/evidence/gap
platformforge analyze cloud-aws ./dumps    # dumps AWS CLI → fatos T1
platformforge analyze ownership ./repo      # ownership.conflicted, não média
platformforge analyze contradictions f.json # declarado ≠ observado → state.contradiction
platformforge judge facts.json             # regras → findings
platformforge judge facts.json --versions '{"kubernetes":"1.29"}'
platformforge graph build facts.json       # fatos → grafo com proveniência
platformforge graph blast --node X         # raio de explosão por classe
platformforge graph identity-become --node role/x  # quem pode assumir o papel
platformforge graph diff --before a.json --after b.json  # diff semântico
platformforge observe slo contrato.yaml --sli '{"total_events":1e6,"bad_events":400}'
platformforge observe postmortem --incident i.json # causa não-resolvida fica nomeada
platformforge finops costs billing.json    # fatos de custo + resumo
platformforge finops ingest cur.csv        # CUR/Azure/GCP/OpenCost/Kubecost → linhas
platformforge finops focus-validate rows.json # conformidade FOCUS 1.0
platformforge finops unit costs.json --denominators d.json  # custo/request etc.
platformforge change review --repo . --patch d.patch  # sandbox → delta de grafo → risco
platformforge product maturity --signals s.json
platformforge product paths                # biblioteca de golden paths
platformforge mcp tools                    # superfície MCP com limites
platformforge mcp serve                    # servidor stdio (mesmo núcleo do CLI)
platformforge lab run-all                  # suite Forge Lab (13 cenários)
platformforge lab chaos lab/chaos-pod-kill # injeção de falha no grafo (simulação)
platformforge evals run                    # framework de avaliação (34 casos)
platformforge evals coverage               # matriz regra ↔ caso (63/63)
platformforge evals precision              # taxa de falso-positivo medida
platformforge store gc                     # GC do store (dry-run por padrão)
platformforge bench run                    # benchmarks medidos (não claim)
platformforge capability list              # registry v2 de capacidades
platformforge capability check --domain k8s --version 1.29
platformforge diagnose <node> --findings j.json --facts f.json
platformforge plan findings.json           # plano de remediação (DAG, v2)
platformforge explain <finding-id>         # cadeia de evidência completa
platformforge recommend findings.json      # recomendações com risco+rollback
platformforge policy check facts.json      # catálogo como política
platformforge security ./dumps             # secrets+iam+sbom+supply bundle
platformforge sdd status --feature F       # ciclo SDD + cascata de hash
platformforge forge manifest               # manifesto de capacidade (interop)
platformforge agents list                  # roster canônico (41 agentes)
platformforge agents check                 # drift gate dos mirrors de host
platformforge agents playbook "tarefa"     # fallback sem subagentes
platformforge agents referee --positions p.json  # debate bounded (10 eixos)
platformforge route '{"task":"...","risk":"high"}' # decisão do Router V2
platformforge fleet report lab/fleets/acme # receipt north-star da frota
platformforge optimize scan lab/fleets/acme  # oportunidades → ChangeIntent
platformforge bench scale                  # bench medido 10k nós/500k arestas
platformforge knowledge                    # freshness do registry de fontes
```

## Pipeline

```
artefatos → analyze → fatos ──► judge → findings ──► scorecards / gates
                 │                                  ▲ rules/catalog/
                 └──────► graph build → graphfy ────┘ (deps, blast, diff)
```

Fatos carregam tiers de evidência (medido → provedor → plano → repo → doc
→ declarado → inferido); T6/T7 nunca viram fatos. Arestas carregam
proveniência `observed | planned | declared | inferred`. Toda mutação
passa por `inspect → propose → sandbox → verify → approve → apply`;
o núcleo nunca muta nada — `approve/apply` recusam no core.

## O que ele responde

Onde o software roda · como chega lá · como é governado · como é
observado · quão confiável · quão seguro · quanto custa · de quem é ·
o que uma mudança pode afetar — e **o que não se sabe**, nomeado com
o que destrava a resposta.

## Docs de design

Índice: [docs/README.md](docs/README.md) — ADRs, docs de agentes,
relatórios de ciclo.

[ARCHITECTURE.md](ARCHITECTURE.md) · [GRAPHFY.md](GRAPHFY.md) ·
[ECONOMY.md](ECONOMY.md) · [SDD.md](SDD.md) · [AGENTIC-OS.md](AGENTIC-OS.md) ·
[FLEET.md](FLEET.md) · [PLATFORM-ANALYTICS.md](PLATFORM-ANALYTICS.md) ·
[OPTIMIZATION.md](OPTIMIZATION.md) · [FEDERATION.md](FEDERATION.md) ·
[OPS.md](OPS.md) · [DOMAIN-MAP.md](DOMAIN-MAP.md) ·
[CAPABILITIES.md](CAPABILITIES.md) · [RESEARCH.md](RESEARCH.md) ·
[ROADMAP.md](ROADMAP.md) · [KNOWLEDGE.md](KNOWLEDGE.md) ·
[RULES.md](RULES.md) · [SECURITY.md](SECURITY.md) · [EVALS.md](EVALS.md) ·
[CLOUD.md](CLOUD.md) · [GOLDEN-PATHS.md](GOLDEN-PATHS.md) ·
[QUALITY-PER-TOKEN.md](QUALITY-PER-TOKEN.md) ·
[CLI-REFERENCE.md](CLI-REFERENCE.md) · [GLOSSARY.md](GLOSSARY.md) ·
[MCP.md](MCP.md) · [docs/agents/](docs/agents/) (runtime agentico) ·
[CONTRIBUTING.md](CONTRIBUTING.md) · [AGENTS.md](AGENTS.md) ·
[CHANGELOG.md](CHANGELOG.md)

## Licença

MIT — veja [LICENSE](LICENSE), [SOURCES.md](SOURCES.md), [CREDITS.md](CREDITS.md).
