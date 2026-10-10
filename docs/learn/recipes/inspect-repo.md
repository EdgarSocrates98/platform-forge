# Receita — postura determinística de um repositório

**O quê:** `platformforge inspect` inventaria artefatos e postura de um repo
em facts com evidence tier.
**Por que:** resposta sobre o repo vem de facts, não de leitura de arquivo.
**Quando:** primeira passada, auditoria, input de `judge`/`analyze <dom>`.
**Quando não:** resposta sobre regras — isso é `judge`/`policy check`.

## Problema

"O que existe neste repo — pipelines, IaC, deps — como facts citáveis?"

## Passo a passo

```bash
platformforge inspect --repo . --offline --detail-level summary --json
```

`--offline` proíbe qualquer adapter com rede; `--strict` faz
`unresolved`/refusal virar exit 2.

## Saída esperada / interpretação

Facts com `fact_id` e tier de evidência — **cite o `fact_id`** ao responder.
`planned ≠ observed`: contradições mostram os dois estados.

## Verificação

Cada fact carrega evidência; `--detail-level full` expande o payload
bounded.

## Limitações

Sem execução, sem provider SDK no core, sem LLM — facts cobrem o observável
e declarado; o que não tem evidência sai como `unresolved`.

## Erros comuns

| Sintoma | Causa | Ação |
|---|---|---|
| `refusal` com `PF-*` | campo/ação fora da política | leia `unlock` na saída |
| exit 2 com `--strict` | unresolved presente | investigue os unresolved |

## Uso por agentes

Contrato do AGENTS.md: *rode o verbo antes de responder*; `--json` default;
`unresolved` é resposta válida — não preencha.
