# Instalação portátil — platform-forge

Instala em qualquer diretório/repositório — sem estrutura prévia exigida
(alvo gitless é primeira classe; veja abaixo).

```bash
cd <qualquer-projeto>
platformforge install                    # escopo projeto (padrão)
platformforge install --dry-run          # planeja sem escrever nada
platformforge install --root /outro/dir  # alvo explícito (vence --repo)
platformforge install --profile minimal  # só config+MCP+state
platformforge install --profile full     # mesmo conjunto de recommended hoje
platformforge install --components skills,mcp   # seleção explícita por kind
```

O que acontece: assets gerenciados vão para `.agents/`, `.claude/`,
`.devin/`, `.codex/` conforme os hosts detectados; `.mcp.json` ganha uma
entrada gerenciada; `AGENTS.md` recebe um bloco delimitado — conteúdo seu
nunca é sobrescrito.

Perfis: `--profile` seleciona CONJUNTOS de componentes — e nada mais.
`minimal` = config+mcp+state; `recommended` = o conjunto completo
(padrão); `full` instala **o mesmo conjunto de `recommended` hoje** —
declarado honestamente, é o slot reservado a defaults mais pesados se
entrarem no pacote. `--components` sobrescreve por kind
(`skills,agents,mcp,knowledge,rules,evals,tui,graph-studio`).

`--gateway-profile economy|balanced|deep` é uma dimensão ortogonal,
persistida como `execution_profile` em `components.json`. Hoje é
**registrado apenas** — o argv de `platformforge-mcp` não tem flag de
modo/surface; nada é fingido na linha de comando.

Alvo: `--root <dir>` declara o alvo explicitamente (a flag que o
orquestrador the-forge sempre envia; `--repo` segue como alias legado).
Sem `--root`, o escopo `project` resolve o cwd — que precisa de um
marcador de projeto (`.git`, `pyproject.toml`, `forge.json`,
`forge.agentic.json` ou `package.json`).
