# Receita — verificar e usar o MCP

**O quê:** `install mcp-verify` faz handshake real (initialize →
tools/list → tools/call) contra `platformforge-mcp`; `mcp tools` lista
as 39 capabilities; `integrate --host <h>` escreve a config local do host.
**Por que:** "o host consegue chamar as tools?" é respondido por um
handshake real, não por arquivo presente.
**Quando:** após `install`/`integrate`, quando uma tool falha no host,
para conferir a superfície publicada.
**Quando não:** para lançar o host — isso é `hosts <h> --launch`; MCP
expõe observação, nunca launch.

## Passo a passo

```bash
platformforge mcp tools                          # registry completo
platformforge integrate --host devin             # escreve .devin/mcp_config.local.json
platformforge install mcp-verify                 # handshake + invoke real
platformforge hosts                              # READY/confirmação por host
```

## Saída esperada / interpretação

`mcp-verify` retorna `status: PASS` com a lista de tools e o invoke da
tool de verificação (`platformforge_inspect`); `BLOCKED` diz o que falta
(binário fora do PATH, install incompleto).

## Verificação

No host: `devin mcp list` deve mostrar `platformforge`. Dentro de uma
sessão, peça "call platformforge_hosts" e compare com `hosts` no CLI.

## Limitações

O verify testa o binário `platformforge-mcp` no PATH — instalação por
fonte exige o venv no PATH ou `pipx install`; configs por host são
`*local.json` (nunca globais).

## Erros comuns

| Sintoma | Causa | Ação |
|---|---|---|
| `BLOCKED: not resolvable on PATH` | launcher ausente | instale/ative o ambiente do pacote |
| host não lista o server | `integrate` não rodou p/ o host | `integrate --host <h>` |

## Uso por agentes

Toda capability do registry é read-only (`readOnlyHint`) salvo as
marcadas `mutable: true` — o boundary de mutação continua no CLI+TTY.
