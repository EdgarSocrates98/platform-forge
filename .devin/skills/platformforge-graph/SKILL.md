---
name: platformforge-graph
description: "Constrói e consulta o grafo de plataforma (Graphfy) a partir de fatos — deps, dependents, blast radius por classe de impacto, paths, gaps, cycles, diff entre snapshots. Use para 'o que essa mudança afeta', 'quem depende deste serviço', mapear ownership/deploy/routing, detectar gaps de observabilidade/segurança e cruzar repos de um workspace.yaml. Não use para extrair fatos (→ analyze) nem para julgar regras (→ judge)."
---

# Graphfy — grafo de plataforma

Grafo é derivado de fatos (`attrs.graph`), nunca de texto livre. Contrato:
`platformforge/graph/v1`; vocabulário em `platformforge/graph/vocab.py` e
`GRAPHFY.md`.

## Verbos

```bash
platformforge graph build facts.json          # grava .platformforge/graph/
platformforge graph stats
platformforge graph deps --node <id>          # transitivo, só arestas de dependência
platformforge graph dependents --node <id>
platformforge graph blast --node <id>         # by_class: reliability/security/…
platformforge graph paths --src A --dst B
platformforge graph gaps                      # nós sem owner/monitoramento/policy
platformforge graph cycles
platformforge graph snapshots                 # ids dos snapshots
platformforge graph diff --before <id> --after <id>
```

## Regras de leitura

- `deps`/`dependents` filtram `DEPENDENCY_KINDS` — `owns` não é dependência.
- `blast` retorna classes separadas + `note`: proximidade ≠ causalidade.
- Edge `inferred` (fatos t6–t7) nunca é apresentada como `observed`.
- Sem grafo construído → recusa `PF-GRAPH-NOGRAPH` com unlock
  (`graph build <facts.json>`); não reinterprete silenciosamente.

## Multi-repo

Fatos vindos de `analyze` sobre raiz de workspace carregam
`attrs.workspace_member`; `graph build` cruza os membros por node id
content-derived (mesma label → mesmo nó → aresta cross-repo).
