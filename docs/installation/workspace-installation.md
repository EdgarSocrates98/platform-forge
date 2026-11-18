# Instalação em workspace — platform-forge

Monorepo/pasta com vários repositórios:

```bash
cd ~/minha-workspace
theforge install auto --scope workspace
# ou membro explícito (repetível):
theforge install auto --scope workspace --member sub/repo
```

Descoberta: diretórios com **qualquer** marcador de projeto até 2 níveis
— `.git` OU um manifesto (`pyproject.toml`, `forge.json`,
`forge.agentic.json`, `package.json`). Membros sem git são primeira
classe. Cada membro mantém seu próprio estado e ledger isolados —
nenhum runtime duplicado. `--root` explícito é autoritativo: a
caminhada de ancestrais nunca sobe acima dele.

Precedência: `project > workspace > user` — instalação local do projeto
vence sempre, e conflitos são reportados, nunca sobrescritos.
