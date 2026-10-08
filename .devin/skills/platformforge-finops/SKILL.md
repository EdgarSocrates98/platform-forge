---
name: platformforge-finops
description: "Analisa custos de plataforma a partir de dados FOCUS/billing — ingestão, resumo por serviço/conta, alocação, economia unitária, anomalias, forecast e custo por nó do grafo. Use para 'quanto custa', fatura, identificar recurso ocioso/caro, alocar custo a serviço/team, preparar ou validar FOCUS, custo unitário. Não use para provisioning (→ analyze iac) nem para SLO (→ platformforge-sre)."
---

# FinOps — custo como cidadão de 1ª classe

Input: billing JSON (FOCUS-prep shape), CSV agregado, ou dumps de
CUR/Azure/GCP/OpenCost/Kubecost via `finops ingest`. Sem API de billing —
analisar dumps, nunca consultar provider.

## Verbos

```bash
platformforge finops costs billing.json        # resumo + findings PF-FIN-*
platformforge finops costs billing.json --by service|account
platformforge finops allocate billing.json     # alocação por declaração
platformforge finops focus billing.json        # pré-normalização FOCUS
platformforge finops focus-validate f.json     # valida spec_version conhecida
platformforge finops unit billing.json         # economia unitária (denominador!)
platformforge finops ingest <dir>              # CUR/Azure/GCP/OpenCost/Kubecost
platformforge finops report <dir>              # relatório composto
platformforge finops graph facts.json          # custo por nó do grafo
```

## Disciplina

- `unallocated` é output legítimo — nunca inventar serviço para fechar 100%.
- Regras PF-FIN-* (ZOMBIE, UNALLOCATED, SPIKE) têm thresholds declarados no
  catálogo; não ajustar pra passar.
- Custo estimado ≠ custo medido — tier da evidência carrega isso.
- Unit economics sem denominador real = recusa, não número fracionado.
- `focus-validate`: `spec_version` desconhecido → `PF-FINOPS-FOCUS-VERSION`
  — versões novas são detectadas, não conformadas.
