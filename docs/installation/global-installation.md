# Instalação global (escopo user) — platform-forge

Instala uma vez para todos os projetos do usuário:

```bash
platformforge install --scope user
```

Escreve em `~/.claude/`, `~/.agents/`, `~/.config/<host>/` e config MCP
global. Combinável com instalações de projeto: o nível mais específico
(`project`) sempre prevalece.
