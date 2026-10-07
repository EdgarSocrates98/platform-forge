---
name: platformforge-economy
description: "Economia de tokens do Platform Forge — TokenSave (conteúdo endereçável, FTS5, context packs bounded), RTK para comandos verbosos, Caveman (compressão lossless), roteamento adaptativo cheap→premium e ledger de custo. Use para 'gastei muito contexto', montar context pack para subagente, decidir barato vs premium, ou auditar gasto de tokens. Não substitui análise de plataforma (→ platformforge-core)."
---

# Economy kernel — tokens como recurso contábil

Módulos: `platformforge/tokensave/` (index FTS5, budget, packs),
`platformforge/economy/` (rtk, caveman, routing, engine) e
`platformforge/knowledge/` (source registry com freshness).

## Verbos

```bash
platformforge knowledge                        # freshness do source registry
platformforge tokens index                     # indexa árvore em .platformforge/index.db
platformforge tokens search "<termo>"          # FTS5
platformforge tokens pack --task "<t>" --input-budget 4000
platformforge tokens stats | tokens ledger     # uso e ledger
platformforge rtk compact --command "cmd" < saida.txt   # spans colapsados
platformforge rtk expand --start S --end E              # lazy expand
platformforge caveman <file> --mode off|lite|full|auto  # compressão lossless
platformforge route '{"task":"...","risk":"low"}'       # TaskSignal → classe
platformforge economy                          # relatório do engine
```

## Disciplina

- Context pack é byte-bounded (`--input-budget`) — excedente vira
  `truncated`, nunca estoura silenciosamente.
- RTK nunca perde dados: spans colapsados restauram via `rtk expand`.
- Route é recomendação de classe, não enforce — `tokens ledger` registra a
  escolha real pra calibrar.
- Dedupe é por content hash — mesmo fato observado duas vezes = um slot.
