# Receita — usar as skills instaladas no host

**O quê:** `install` projeta as 12 skills `platformforge-*` em
`.devin/skills/`, `.claude/skills/`, `.agents/skills/` — o host as
descobre nativamente na sessão seguinte.
**Por que:** a skill é o manual operável do agente — diz quando entrar,
quando não entrar e qual verbo resolve.
**Quando:** depois de instalar, para perguntas como "analise minha
plataforma", "o que essa mudança afeta", "quanto custa" — a skill certa
dispara ou você a invoca pelo nome.
**Quando não:** antes do `install` — sem mirrors não há o que descobrir.

## Passo a passo

```bash
platformforge install apply --repo . --yes       # projeta skills+agents+mcp
platformforge install status --repo .            # healthy = descoberta ok
platformforge hosts                              # READY = host pronto p/ abrir
```

Depois, dentro do host: `use the platformforge-graph skill` (ou deixe o
gatilho natural da pergunta disparar).

## Saída esperada / interpretação

`install status` mostra checks `pf:*` PASS; as skills aparecem em
`.devin/skills/platformforge-*/SKILL.md` — cada uma roteia para a
vizinha quando a pergunta sai do domínio.

## Verificação

`platformforge hosts devin` mostra `integration: healthy` quando os
assets estão todos no lugar — é a medida real, não a presença do arquivo.

## Limitações

Skills são documentação operável — o poder está nos verbos/engines que
elas chamam; skill sem install é texto sem engine no PATH.

## Erros comuns

| Sintoma | Causa | Ação |
|---|---|---|
| host não vê skills | install nunca rodou ali | `install apply --repo <proj>` |
| `unverified` no `hosts` | sem recibo de install | `install status` mostra o que falta |

## Uso por agentes

`platformforge-core` é o ponto de entrada ("analise minha plataforma") e
roteia para `platformforge-graph`, `-security`, `-sre`, `-finops`,
`-agents` conforme o domínio emerge.
