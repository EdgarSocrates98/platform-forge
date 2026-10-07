---
name: platformforge-sdd
description: "Conduz mudanças no próprio Platform Forge pelo SDD nativo — feature dir com intent/design/plan/tasks, cascata de hashes (mudança upstream invalida downstream), gates por evidência, override com recibo. Use ao iniciar feature/fase, quando `sdd check` recusar, ou para fechar uma fase com gate. Não use para analisar plataformas de usuário (→ platformforge-core)."
---

# SDD nativo — fases e gates

Cada feature vive em `sdd/<FEATURE>/`. Fases na ordem:

```text
init → discover → define → design → contract → plan → build → review →
verify → ship → learn
```

Cascata de hashes: mudar uma fase upstream invalida as downstream
(stale → `sdd check` falha até `sdd stamp` re-selar).

## Verbos

```bash
platformforge sdd init --feature F --body "objetivo"
platformforge sdd design --feature F --body "..."
platformforge sdd status --feature F       # fases: current/stale/blocked
platformforge sdd check --feature F --phase plan --verify "pytest -q"
platformforge sdd stamp --feature F --phase plan   # re-sela após editar
platformforge sdd ship --feature F --override --override-reason "porquê"
```

## Disciplina

- Gate falha porque upstream está stale ou evidência ausente — corrija o
  artefato e `sdd stamp`; não use `--override` pra esconder dívida
  (o recibo fica registrado).
- `sdd check --verify "cmd"` roda o comando e anexa o resultado como
  evidência da fase.
