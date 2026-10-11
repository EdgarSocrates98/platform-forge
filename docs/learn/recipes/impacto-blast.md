# Receita — blast radius e impacto de uma mudança

**O quê:** `graph blast --node <n>` calcula o que uma mudança atinge;
`impact --node` é o atalho; `change review` faz a mesma pergunta com
risco decomposto.
**Por que:** "o que quebra se eu mexer aqui" vira traversal com
provenance — cada nó impactado cita a aresta que o liga.
**Quando:** antes de mudar um serviço/recurso; ordenar remediação;
avaliar PR de infra.
**Quando não:** sem grafo construído — `graph build facts.json` antes;
sem facts — `analyze`/`collect` primeiro.

## Passo a passo

```bash
platformforge graph build facts.json             # materializa nós+arestas
platformforge graph stats                        # confirma o que entrou
platformforge graph blast --node <id>            # raio de impacto
platformforge graph dependents --node <id>       # quem depende dele
platformforge impact --node <id>                 # alias de alto nível
```

## Saída esperada / interpretação

Lista de nós afetados com a aresta que os liga ao alvo; blast vazio é
resposta ("nó folha ou sem edges observadas"), não falha.

## Verificação

`graph diff --before a.json --after b.json` entre dois states mede o que
a mudança real faria no grafo — gate honesto de regressão.

## Limitações

O grafo só conhece dependências que viraram facts — integração
implícita/_runtime-only_ não aparece sem uma observação (`live`).

## Erros comuns

| Sintoma | Causa | Ação |
|---|---|---|
| `PF-GRAPH-NOGRAPH` | grafo não construído | `graph build <facts.json>` (o unlock está no recibo) |
| nó não achado | id errado | liste nós com `graph stats`/facts |

## Uso por agentes

`platform-change-coordinator` encadeia blast → risk → policy → approval
sem executar — `change review` é a mesma análise end-to-end.
