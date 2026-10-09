# Uninstall — platform-forge

```bash
platformforge uninstall            # remove só arquivos gerenciados
platformforge uninstall --purge    # + remove o estado local (.platformforge/)
```

O ledger SHA-256 decide ownership: arquivos que você criou ou modificou
depois da instalação ficam no lugar (reportados como `kept`). Diretórios
que esvaziam são podados; os seus permanecem.
