# Quickstart — platform-forge

Três comandos:

```bash
git clone <platform-forge repo>
cd platform-forge
./install.sh      # Windows: .\install.ps1 — account runtime + editable CLI
```

Depois, dentro de qualquer projeto:

```bash
cd ~/meu-projeto
platformforge install
```

Pronto. Abra seu AI host (Devin, Claude, Codex ou Copilot) — as skills do
platform-forge já estão instaladas.

Em diretório vazio, escolha `Entire workspace`: o manifesto
`.platformforge/workspace.json` é criado durante o apply. `Current repository`
fica disponível apenas quando há VCS detectado.

## Verificar

```bash
platformforge status
platformforge doctor
```

Detalhes: [account-installation.md](account-installation.md). Problemas? → [troubleshooting.md](troubleshooting.md)
