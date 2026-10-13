---
name: platformforge-agents
description: "Runtime agentico do Platform Forge (Cycle 5.1) — roster canônico de 41 agentes (orquestração, coordenadores, especialistas, reviewers, executors), Router V2 com DAG + budgets, dispatch bounded, debate bounded com referee, verificação independente, context packs e ledger de runs, mirrors de host gerados e playbook zero-subagent. Use para 'qual agente pega isso', rotear tarefa complexa, sincronizar mirrors de host (.claude/.codex/.devin/.agents), checar drift de mirrors, montar playbook sem subagentes, arbitrar conflito entre especialistas, ou auditar orçamento/independência de agentes. Agentes nunca mutam produção — ação governada fica no host."
---

# Agentic runtime — agentes operam engines, não as substituem

Roster canônico: `platformforge/agents/roster.py` (41 agentes).
Mirrors são **gerados, nunca editados**: `agents/`, `.agents/agents/`,
`.claude/agents/`, `.codex/agents/`, `.devin/agents/` (205 arquivos).

## Verbos

```bash
platformforge agents list                    # roster (41)
platformforge agents lint                    # contract lint
platformforge agents sync                    # regenera os 5 targets
platformforge agents check                   # drift: missing/stale/stray
platformforge agents playbook "<task>"       # fallback zero-subagent
platformforge agents referee --positions p.json  # debate bounded
platformforge agents bench                   # estratégias comparadas (projeção)
platformforge route '{"task":"...","risk":"high","production":true}'
```

Router V2 modos: `deterministic` (zero agentes) → `single-specialist` →
`multi-specialist` → `coordinated` → `debate` → `critical-review`.

## Regras duras (garantidas por gate/teste)

- Produtor nunca é seu próprio verificador (`PF-AGENT-INDEPENDENCE`).
- Rota crítica/produção exige ops-safety + security reviewers + verifier.
- Posição de debate sem evidência é recusada; rounds ≤ 3; referee emite
  `winner|tied|unresolved` — e não substitui o verifier.
- Exaustão de budget → `partial`, nunca sucesso silencioso; resume nunca
  reseta budget gasto.
- Contexto é pack de grafo+evidência bounded — nunca o repo inteiro;
  follow-up recebe `previous_hash + delta`.
- Nenhum spec de agente lista verbo de mutação; `change approve|apply`
  continua host-side (`PF-OPS-*`).
- Rota que referencia agente inexistente falha no `agents-routing` gate.

## Boundaries

- Mirror não pode conceder permissão que o contrato não declara.
- `agents playbook` carrega os mesmos requisitos de evidência e
  verificação da rota agentica — degrada paralelismo, não rigor.
- Verificação e reporte de `unresolved` são isentos de budget.
