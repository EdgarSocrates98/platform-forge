# Receita — usar o roster de agents

**O quê:** 41 agentes canônicos (orquestrador, coordenadores,
especialistas, reviewers, executors) com Router V2 + DAG + budgets;
`agents list/lint/check/playbook/referee/bench` operam o roster.
**Por que:** pergunta cross-domain vira decomposição declarada —
o orquestrador roteia para o especialista certo com orçamento e
verificação independente.
**Quando:** "qual agente pega isso", rotear tarefa complexa, checar
drift dos mirrors, montar playbook sem subagentes.
**Quando não:** mutação de produção — agents nunca aplicam; ação
governada fica no host (`change approve|apply` recusam no core).

## Passo a passo

```bash
platformforge agents list                        # roster com papel/domínio
platformforge agents playbook platform-orchestrator  # decomposição passo a passo
platformforge agents check                       # drift dos mirrors gerados
platformforge agents sync                        # regenera mirrors de host
platformforge agents referee --help              # arbitrar desacordo
```

## Saída esperada / interpretação

`list` mostra id/papel/domínios; `check` compara mirrors gerados com o
roster — drift é diff de conteúdo, nunca silêncio.

## Verificação

`agents lint` valida contratos (`when_to_enter`/`when_not_to_enter`,
handoffs); `agents bench` mede estratégias de roteamento sobre cases.

## Limitações

Mirrors em `.claude/`, `.agents/`, `.codex/`, `.devin/` são **gerados** —
edite o roster (`platformforge/agents/roster.py`), nunca o mirror.

## Erros comuns

| Sintoma | Causa | Ação |
|---|---|---|
| `agents` bare falha | exige subcomando | `agents list` é o ponto de partida |
| drift no `check` | mirror editado na mão | `agents sync` regenera |

## Uso por agentes

Num host, peça pelo nome: "use the platform-orchestrator profile to map
this platform" — ou rode `agents playbook` quando não houver subagentes.
