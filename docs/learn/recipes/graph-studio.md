# Receita — Graph Studio e visualização do grafo

**O quê:** `graph ui` abre o Graph Studio (servidor local + browser) sobre
o grafo construído; `graph view` emite o descriptor/JSON para outras
visualizações; `graph snapshots` gerencia versões.
**Por que:** navegação visual das dependências — nós, arestas, camadas —
sobre o mesmo grafo com provenance que `blast` consulta.
**Quando:** apresentar a plataforma, explorar topologia, depurar uma
resposta de `blast`/`paths` vendo as arestas.
**Quando não:** sem grafo — `graph build facts.json` primeiro (a recusa
`PF-GRAPH-NOGRAPH` já traz o comando de desbloqueio).

## Passo a passo

```bash
platformforge graph build facts.json             # materializa
platformforge graph ui                           # serve + abre o browser
platformforge graph ui --no-browser --port 8901  # só serve (CI/SSH)
platformforge graph view                         # descriptor JSON
platformforge graph snapshots                    # versões do grafo
```

## Saída esperada / interpretação

`ui` sobe um servidor local (read-only sobre o grafo corrente);
`view` emite o descriptor com `available_layers`/`queries` — o mesmo
contrato que a UI consome.

## Verificação

`graph stats` (ou `ui` + stats na UI) deve mostrar os mesmos nós/arestas
que `graph build` contou — divergência é bug de store.

## Limitações

O Studio renderiza o que o grafo tem — camadas sem facts não aparecem;
`--no-browser` é o caminho headless/CI.

## Erros comuns

| Sintoma | Causa | Ação |
|---|---|---|
| `PF-GRAPH-NOGRAPH` | grafo ausente | `graph build <facts.json>` |
| browser não abre | headless/SSH | `--no-browser --port <p>` e abra manual |

## Uso por agentes

`platform-graph-specialist` responde "quem depende deste serviço" sobre o
mesmo grafo — a UI é a mesma evidência em formato navegável.
