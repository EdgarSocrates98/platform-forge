# SDD Baseline — platform-forge (Onda 0)

- SHA `3cb36770bb3b` · branch `release/cycle-2.7-patch-version` · `.git` present · ~130 dirty files (pre-existing user changes — untouched)
- Python ≥3.10 · pytest suite: `tests/test_sdd.py` = **5 tests pass** (baseline)
- SDD: `platformforge/sdd/lifecycle.py` (239 ln, só módulo) · 10 fases `discover..learn` · root `.platformforge/sdd` (gitignored)
- Skill canônica `platformforge/data/portable_skills/platformforge-sdd/SKILL.md`; mirror `.devin/skills/` byte-parity
- CLI `platformforge sdd init|discover|..|check|stamp|ship|learn` (`cli/main.py:3170`, handler :836)

## Findings

| # | Sev | Finding | Evidência |
|---|---|---|---|
| F1 | P0 | `check()` = apenas "sem stale" — feature vazia → `ok:True`; sem validação de schema/conteúdo/faltantes | lifecycle.py:163-165 |
| F2 | P0 | `ship_gate` nunca lê evidências do disco — confia em `verify`/`findings`/`risk` do caller; existence ⇒ aprova | :200-218 |
| F3 | P0 | `stamp()` promove massivamente a `ready` sem aprovação — stamping IS approval; clobber `accepted` | :167-189 |
| F4 | P1 | `critical_finding_unresolved` inalcançável via CLI — sem `--findings` | main.py:858-866 |
| F5 | P1 | risk gate opt-in — omitir `risk` desativa | :216-218 |
| F6 | P1 | SKILL.md documenta `--verify "cmd"` que o CLI ignora; `evidence[]` nunca populado | SKILL.md:26,37 |
| F7 | P1 | Artefatos SDD + receipts sob `.platformforge/` gitignored → auditoria efêmera | .gitignore:9-13 |
| F8 | P1 | Ordem de fases diverge docs (AGENTS.md:45 `contract→design` vs código `design→contract`) | lifecycle.py:22 |
| F9 | P2 | `sdd init` retorna `initialized` mas não cria nada | main.py:842 |
| F10 | P2 | Taxonomia status incoerente (código só emite `ready`) | :110 |
| F11 | P2 | Cascade: upstream deletado/ausente nunca stale | :147-159 |
| F12 | P2 | Validadores de plataforma (iac/k8s/gitops/iam/sbom/observe) existem mas não integrados | módulos em platformforge/ |

## Capacidades preservadas

Cascade sha256 upstream, gate_failure taxonomy, override receipt, 10 fases, frontmatter sdd:1, feature-name traversal block.
