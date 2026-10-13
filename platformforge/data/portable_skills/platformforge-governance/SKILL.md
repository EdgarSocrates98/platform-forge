---
name: platformforge-governance
description: "Governança do próprio Platform Forge e da plataforma analisada — freeze de arquitetura (manifest, snapshots, check de drift de contrato, FeatureException/RFC de unfreeze), corpus de evidência (cases golden/holdout, replay determinístico, ledgers de falso positivo/negativo, route-audit, context-audit), evals (coverage/precision), policy-as-code (`policy check`) e platform product (maturity, scorecard, golden paths, Backstage). Use quando `freeze check` falhar, antes de mudar roster/schema/CLI/capabilities, para decidir se uma mudança cabe no freeze ou exige exceção, para adicionar caso/eval de regressão, auditar precisão de regras, checar políticas ou medir maturidade/golden path. Não use para revisar mudança de infra do usuário (→ platformforge-change) nem para fluxo de fases de feature (→ platformforge-sdd)."
---

# Governança — freeze, evidência, policy, produto

Estado atual: **ARCHITECTURE FROZEN** (`docs/freeze/LIFECYCLE.md`). O
freeze é o default; quem quer mudar arquitetura carrega o ônus da prova.

## Freeze

```bash
platformforge freeze check                    # drift de contrato + gate de exceções
platformforge freeze manifest                 # superfície congelada atual
platformforge freeze snapshot                 # recalcula hashes (só com exceção aprovada)
platformforge freeze exception --spec docs/freeze/exceptions/FE-XXX.json
```

Snapshots em `docs/freeze/snapshots/` hasheiam **todo campo** de
agents (`roster.py`), capabilities, CLI, MCP e schemas. Consequência
prática:

- Mudar texto no `roster.py` (até descrição) = `breaking` no
  `freeze check`. Ajuste de apresentação vai no renderer
  (`agents/mirrors.py`), que não é snapshotado.
- Cabe no freeze sem review: bug-fix, performance-fix (com receipt),
  security-fix, knowledge-update, new-eval, fixture real sanitizada,
  compatibilidade, documentação.
- Exige FeatureException (`FE-000-template.json`): subsistema novo,
  família de schema pública, nível de autonomia, control plane, pilar de
  domínio, expansão grande de roster. Precisa de `real_world_blocker`
  nomeado + evidência — "seria legal" é não-razão explícita (§210).
- `freeze snapshot` sem exceção aprovada esconde drift — não rode para
  "deixar verde".

## Corpus de evidência

```bash
platformforge cases list|validate                 # .platformforge/cases/<golden|holdout>/<id>/case.yaml
platformforge cases template [--out f]          # esqueleto de case (grava case.yaml no cwd)
platformforge cases replay [--tier golden]        # replay determinístico, hash canônico
platformforge cases ledger | ledger-check         # FP/FN: todo registro aponta regressão
platformforge cases route-audit | route-bench     # Router V2 sobre o corpus
platformforge cases context-audit --stamp         # context_cost medido
platformforge evals list|run|coverage|precision [--type T]
```

- Defeito real encontrado → registro no ledger **e** case de regressão;
  `ledger-check` falha se o ponteiro não resolve.
- `holdout` não é usado para calibrar — só para medir. Ajustar regra
  olhando holdout invalida a medição.
- Replay é determinístico: hash diferente sem mudança de código é bug,
  não flakiness.

## Policy e produto

```bash
platformforge policy list | policy check <path>
platformforge product maturity|scorecard|capabilities [--facts f --findings f]
platformforge product paths | product path --id <id> | product path-analyze
platformforge product backstage [--facts f]
```

- Maturity/scorecard derivam de facts+findings — passe `--facts`/`--findings`
  do repo analisado; sem eles o score reflete só sinais declarados.
- Métricas de DX são por time, nunca individuais.

## Fronteira

- `ops`/`live` são boundary do host (níveis S0–S5, `--execute`, aprovação
  humana). Esta skill audita, não executa — mutação governada pertence a
  `platformforge-change` + gate humano.
- Receipts (`docs/freeze/*-RECEIPT.json`) são ligados a um SHA medido;
  nunca edite à mão para refletir commit novo — regenere pela via que os
  produziu.
