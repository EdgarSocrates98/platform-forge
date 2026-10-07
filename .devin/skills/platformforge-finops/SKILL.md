---
name: platformforge-finops
description: "Analisa custos de plataforma a partir de dados FOCUS/billing — ingestão, resumo por serviço/conta, alocação, economia unitária, anomalias e custo por nó do grafo. Use para 'quanto custa', fatura, identificar recurso ocioso/caro, alocar custo a serviço/team, preparar FOCUS. Não use para provisioning (→ analyze iac) nem para SLO (→ platformforge-sre)."
---

# FinOps — custo como cidadão de 1ª classe

Input: billing JSON (FOCUS-prep shape) ou CSV agregado. Sem API de billing —
analisar dumps, nunca consultar provider.

## Verbos

```bash
platformforge finops costs billing.json        # resumo + findings PF-FIN-*
platformforge finops costs billing.json --by service|account
platformforge finops allocate billing.json     # alocação por declaração
platformforge finops focus billing.json        # pré-normalização FOCUS
platformforge finops graph facts.json          # custo por nó do grafo
```

## Disciplina

- `unallocated` é output legítimo — nunca inventar serviço para fechar 100%.
- Regras PF-FIN-* (ZOMBIE, UNALLOCATED, SPIKE) têm thresholds declarados no
  catálogo; não ajustar pra passar.
- Custo estimado ≠ custo medido — tier da evidência carrega isso.
