# Receita — hosts: observar e abrir a IA no projeto

**O quê:** `platformforge hosts` mede cada host de IA (binário, versão,
auth, integração com o repo); `hosts <h> --launch` abre o host no
diretório do projeto — `integrate --host <h>` faz o setup.
**Por que:** "meu host está pronto para a forja?" vira medição real —
detectado, autenticado, integrado — não adivinhação.
**Quando:** depois do `install`, antes de uma sessão; para abrir o host
já no contexto do projeto; para saber por que não abriu.
**Quando não:** instalar skills/mirrors — isso é `install apply`;
`hosts` só observa e lança.

## Passo a passo

```bash
platformforge hosts                     # todos: claude/devin/codex/copilot
platformforge hosts devin               # um host
platformforge hosts devin --launch      # abre o REPL no repo (só TTY)
platformforge integrate --host devin    # escreve a config local do host
platformforge install mcp-verify        # handshake real do server
```

## Saída esperada / interpretação

Estados: `NOT_DETECTED` (sem binário) → `DETECTED` → `SUPPORTED` →
`NEEDS_LOGIN` (com `login_hint`) → `READY` (integração `healthy`).
`launch_refused` diz o motivo exato (`host_absent`, `login_required`,
`no_tty`) — nunca silêncio.

## Verificação

No host aberto: `devin mcp list` deve mostrar `platformforge` e as skills
`.devin/skills/platformforge-*` já estão no disco para a sessão.

## Limitações

Launch exige TTY e host autenticado — sem TTY o recibo traz
`launch_command` para colar; o fluxo nunca pede credencial em prompt
nem lança host deslogado. Copilot não tem subcomando de status — auth
fica `None` (desconhecido honesto).

## Erros comuns

| Sintoma | Causa | Ação |
|---|---|---|
| `NEEDS_LOGIN` | sessão expirada | rode o `login_hint` do recibo |
| `READY` nunca | install nunca rodou no repo | `install apply --repo .` |
| `no_tty` | rodou em pipe/CI | abra um terminal ou use `launch_command` |

## Uso por agentes

`platformforge_hosts` (MCP) devolve a mesma observação read-only para o
host consultar o próprio estado — launch continua boundary humano.
