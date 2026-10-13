# Receita — o que depende de quê?

**O quê:** `platformforge graph deps|blast|paths` responde dependência e
impacto sobre o grafo de facts.
**Por que:** "o que quebra se eu mexer aqui" é traversal, não chute.
**Quando:** impact analysis, blast radius, ordenação de remediação.
**Quando não:** inventário — `inspect`; veredito — `judge`.

## Passo a passo

```bash
platformforge graph deps --help       # formas de consulta
platformforge graph blast --help      # blast radius de um nó
platformforge impact --help           # alias de alto nível
```

## Saída esperada / interpretação

Nós e arestas com provenance; ausência de caminho é resposta — não force
uma cadeia que o grafo não tem.

## Verificação

`graph diff` entre dois facts docs mostra o que mudou — bom gate de
regressão de arquitetura.

## Limitações

O grafo cobre o que facts registraram — edges não observadas não existem;
não infere dependência implícita.

## Erros comuns

| Sintoma | Causa | Ação |
|---|---|---|
| nó não achado | facts ainda não coletados | `inspect`/`collect` antes |
| blast vazio | nó folha ou sem edges | confirme com `graph deps` |

## Uso por agentes

`diagnose` junta facts+findings+blast numa resposta só — prefira quando a
pergunta for "o que está errado e o que afeta".
