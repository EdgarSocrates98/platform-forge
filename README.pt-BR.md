# Platform Forge

**Plataforma de inteligência em Platform Engineering** — determinística,
offline-first, evidence-first, grafo-ciente, neutra a provedor no núcleo.

O Platform Forge lê repositórios, Terraform/OpenTofu, Kubernetes, GitOps,
CI/CD, observabilidade, SLOs, segurança, custo e ownership — e constrói um
modelo coerente e auditável da plataforma. Fatos têm proveniência; findings
citam evidência; perguntas sem resposta voltam como recusas nomeadas —
nunca texto evasivo.

## Instalação

```bash
pip install -e .            # núcleo — funciona offline
pip install -e ".[dev]"     # + testes/lint
# ou: uv sync && uv pip install -e .
```

## Início rápido

```bash
platformforge doctor                       # saúde do ambiente
platformforge init --repo .                # scaffolding .platformforge/
platformforge inspect --repo .             # inventário de artefatos
platformforge analyze iac ./infra          # HCL → fatos
platformforge analyze k8s ./manifests      # manifests → fatos
platformforge judge facts.json             # regras → findings
platformforge graph build facts.json       # fatos → grafo com proveniência
platformforge graph blast --node X         # raio de explosão por classe
platformforge observe slo contrato.yaml --sli '{"total_events":1e6,"bad_events":400}'
platformforge finops costs billing.json    # fatos de custo + resumo
platformforge mcp tools                    # superfície MCP com limites
platformforge lab run-all                  # suite de cenários Forge Lab
platformforge sdd status --feature F       # ciclo SDD + cascata de hash
```

## Pipeline

```
artefatos → analyze → fatos ──► judge → findings ──► scorecards / gates
                 │                                  ▲ rules/catalog/
                 └──────► graph build → graphfy ────┘ (deps, blast, diff)
```

Fatos carregam camadas de evidência (medido → provedor → plano → repo →
doc → declarado → inferido). Arestas do grafo herdam proveniência. Toda
mutação passa por `inspect → propose → sandbox → verify → approve →
apply`; o núcleo nunca muta nada.

## Docs de design

[ARCHITECTURE.md](ARCHITECTURE.md) · [GRAPHFY.md](GRAPHFY.md) ·
[ECONOMY.md](ECONOMY.md) · [SDD.md](SDD.md) · [AGENTIC-OS.md](AGENTIC-OS.md) ·
[ROADMAP.md](ROADMAP.md)

## Licença

MIT — veja [LICENSE](LICENSE), [SOURCES.md](SOURCES.md), [CREDITS.md](CREDITS.md).
