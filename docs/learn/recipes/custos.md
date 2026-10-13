# Receita — FinOps: custo, alocação e economia unitária

**O quê:** `finops costs|allocate|unit|report` sobre billing
FOCUS/CSV/exports; `finops focus-validate` checa um export FOCUS;
`finops graph` projeta custo por nó do grafo.
**Por que:** "quanto custa / quem gasta / onde está ocioso" respondido
sobre o dado real de billing — sem baseline medido, nenhuma economia é
prometida.
**Quando:** fatura subiu, alocar custo a serviço/team, achar recurso
ocioso, validar export FOCUS.
**Quando não:** sem arquivo de billing — `finops` lê dados, não consulta
a cloud; provisioning é outra receita (`terraform`).

## Passo a passo

```bash
platformforge finops costs billing.csv            # resumo por serviço/conta
platformforge finops allocate billing.csv         # atribuição
platformforge finops unit billing.csv             # economia unitária
platformforge finops focus-validate focus.parquet # conformidade FOCUS 1.0
platformforge finops report billing.csv           # relatório consolidado
```

## Saída esperada / interpretação

Custos agrupados, anomalias, ocioso/rightsizing; sem billing file a
resposta é a recusa nomeada `PF-FINOPS-NO-INPUT` com o comando de
desbloqueio — nunca um crash de filesystem.

## Verificação

`finops graph` (após `graph build`) amarra custo ao nó — o mesmo número
sob dois ângulos deve bater.

## Limitações

Qualidade do input manda: CUR/Azure/GCP/OpenCost/Kubecost entram por
`ingest`; colunas faltantes viram `unresolved`, não estimativa.

## Erros comuns

| Sintoma | Causa | Ação |
|---|---|---|
| `PF-FINOPS-NO-INPUT` | verbo sem arquivo | `finops <verb> <billing.json|csv>` |
| alocação incompleta | tags/contas ausentes no billing | enriqueça o export e rode de novo |

## Uso por agentes

`platform-finops-specialist` decompõe evidência de custo em findings;
`platform-optimization-coordinator` transforma em recomendação —
execução continua host-side.
