# Platform Forge — trilha de aprendizado

| Nível | Caminho |
|---|---|
| **Iniciante** | [Quickstart](../installation/quickstart.md) → [first-run](../tutorials/first-run.md) → receita [inspecionar repo](recipes/inspect-repo.md) |
| **Intermediário** | [inspect](recipes/inspect-repo.md) → [judge/policy](recipes/judge-policy.md) → [graph deps](recipes/graph-deps.md) → `platformforge doctor` |
| **Avançado** | `finops`/`observe`/`change review` → `evals`/`lab` → SDD (`platformforge sdd`) |
| **Contribuidor** | [CONTRIBUTING](../../CONTRIBUTING.md) → `AGENTS.md` (verb-before-answer) → roster `platformforge/agents/roster.py` |
| **Agente (IA)** | [AGENTS](../../AGENTS.md) — *rode o verbo antes de responder*; cite `fact_id`/`rule_id`; `unresolved`/`refusal` nunca vira resposta preenchida |

## Receitas (problema → solução)

| Tenho este problema | Receita |
|---|---|
| "Postura determinística deste repo" | [inspect-repo](recipes/inspect-repo.md) |
| "O que as regras dizem dos facts?" | [judge-policy](recipes/judge-policy.md) |
| "O que depende de quê?" | [graph-deps](recipes/graph-deps.md) |
| "Auditar Terraform/IaC" | [terraform](recipes/terraform.md) |
| "Auditar Kubernetes/Helm" | [kubernetes](recipes/kubernetes.md) |
| "Auditar pipelines CI/CD" | [cicd](recipes/cicd.md) |
| "O que essa mudança atinge?" | [impacto-blast](recipes/impacto-blast.md) |
| "Postura de segurança" | [seguranca](recipes/seguranca.md) |
| "SLO/error budget aguenta?" | [sre](recipes/sre.md) |
| "Quanto custa / quem gasta?" | [custos](recipes/custos.md) |
| "Qual agente pega isso?" | [usar-agents](recipes/usar-agents.md) |
| "Usar as skills no host" | [usar-skills](recipes/usar-skills.md) |
| "O MCP está respondendo?" | [verificar-mcp](recipes/verificar-mcp.md) |
| "Ver o grafo no browser" | [graph-studio](recipes/graph-studio.md) |
| "Meu host de IA está pronto?" | [hosts](recipes/hosts.md) |

Hub do ecossistema (descoberta cross-forge): `the-forge/docs/hub/` — install, which-forge, hosts, MCP, troubleshooting.

Índice gerado: [../INDEX.md](../INDEX.md).
