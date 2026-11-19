# Update e repair — platform-forge

Reinstalar (`platformforge install --yes` num alvo já instalado) é
incremental: assets byte-idênticos entram no plano como `identical` e
não são reescritos — só `creates` e `managed_updates` tocam o disco.
O receipt registra o plano; o bloco `lifecycle`
(`forge/InstallLifecycle/v1`) deriva a posição honesta da instalação
(`verified` quando as verificações passam, nunca só "completed").

## Update

```bash
platformforge install update --to <versão ou tag pinada>
```

`latest` é recusado por contrato — sempre pin a versão. Sem checkout
registrado o update reporta BLOCKED honestamente.

## Repair

```bash
platformforge doctor   # mostra o drift
platformforge install repair   # reassegura regiões gerenciadas
```

Repair restaura arquivos gerenciados removidos e cura blocos
`platform-forge:managed` dentro de arquivos seus — conteúdo fora do bloco nunca
é tocado. Antes de sobrescrever, um snapshot vai para
`<state_dir>/backups/`.
