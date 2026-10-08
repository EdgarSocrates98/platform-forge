---
name: platformforge-core
description: "Ponto de entrada do Platform Forge para 'analise minha plataforma' e qualquer pergunta cross-domain — inventário de artefatos, fatos com tiers de evidência, findings por catálogo de regras, grafo com proveniência, recusas nomeadas e recibos. Use para auditoria de plataforma, onboarding a um workspace desconhecido, ou quando ainda não está claro qual especialista assume. Roteia para as skills de domínio (graph, change, sre, finops, security, sdd, lab, economy, fleet, agents) assim que a área ficar clara. Não substitui as especializadas."
---

# Platform Forge — core

Protocolo determinístico, offline-first, read-only. Toda resposta cita
`fact_id`/`rule_id`; sem evidência, devolva recusa nomeada — nunca prosa
evasiva.

## Rota canônica

```bash
platformforge doctor                       # ambiente OK?
platformforge init --repo <root>           # scaffold .platformforge/ + workspace.yaml
platformforge inspect --repo <root>        # inventário (workspace-aware, §126)
platformforge analyze <dom> <path>         # iac|plan|state|drift|k8s|gitops|gha|iam|sbom|
                                           # secrets|supply|catalog|crossplane|helm|kustomize|
                                           # hubble|kyverno|cosign|slsa|ownership|contradictions|
                                           # cloud-aws|cloud-azure|cloud-gcp
platformforge judge facts.json             # regras → findings
platformforge graph build facts.json       # grafo com proveniência
platformforge graph blast --node <id>      # raio de explosão por classe
platformforge risk --node <id>             # risco decomposto (§130)
platformforge explain <findings.json> --name <rule_id>
platformforge recommend <findings.json>
platformforge forge manifest               # capacidades publicáveis
platformforge capability check --domain <d> --version <v>
```

## Disciplina

- Fatos têm tier 0–7; tiers 6–7 (LLM/conjectura) nunca viram `Fact`.
- Arestas do grafo herdam proveniência (`observed`/`declared`/`inferred`);
  proximidade no grafo não é causalidade.
- `planned ≠ observed` — contradições mostram os dois estados.
- Sem segredo em output — `core/redaction.py` roda antes de qualquer pack.
- Multi-repo: apontar para a raiz do `workspace.yaml` faz fan-out pelos
  membros e tagueia `attrs.workspace_member`.
- Mutação real nunca acontece no core — ver `platformforge-change`;
  `ops`/`live` são namespaces de boundary do host.

## Quando rotear

- "o que isso afeta / quem depende" → **platformforge-graph**
- mudança, PR, diff, terraform plan, aplicação → **platformforge-change**
- SLO, incidente, capacity, OTel → **platformforge-sre**
- custo, alocação, FOCUS → **platformforge-finops**
- IAM, secrets, SBOM, supply chain → **platformforge-security**
- feature/mudança no próprio platform-forge → **platformforge-sdd**
- cenário de avaliação, fixture dourada → **platformforge-lab**
- tokens, packs, roteamento adaptativo → **platformforge-economy**
- frota, multi-cluster, optimize, federation, AI platform →
  **platformforge-fleet**
- dispatch de agentes, rota Router V2, mirrors, debate, verificação →
  **platformforge-agents**
