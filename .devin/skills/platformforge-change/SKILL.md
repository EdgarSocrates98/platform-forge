---
name: platformforge-change
description: "Revisa mudanças sem tocar a árvore original — sandbox copy → apply patch/files → analyze before/after → compare findings e delta de fatos, depois risco decomposto (blast radius, criticality declarada, produção, identidade, exposição, dados, disponibilidade, custo, reversibilidade, cobertura). Use para revisão de PR/mudança, 'posso aplicar este terraform?', diff de manifests, avaliar risco de uma alteração. O core nunca aplica: approve/apply retornam recusa com boundary host-side."
---

# Change review — §85–86, §130–132

Lifecycle: `propose → sandbox → verify → review → approve → apply`.
O core cobre até `review`; `approve`/`apply` são boundary do host e o CLI
responde `platform.change.core_read_only` com o unlock.

## Fluxo

```bash
platformforge change verify --patch change.diff        # sandbox: antes×depois
platformforge change verify --file infra/main.tf=novo.tf
platformforge change review <intent.json>              # verdict + evidence
platformforge risk --node <grafo-id>                   # sinais derivados do blast
platformforge risk --signals '{"production":true,"reversibility":false}'
platformforge explain findings.json --name PF-IAC-010  # cadeia de evidência
platformforge recommend findings.json                  # Recommendations válidas
```

## Leitura do output

- `delta.fact_kinds_added/removed/changed_count` + `facts_added/removed`.
- `risk.level` ∈ low|medium|high|critical com `decomposition` por sinal —
  sinais ausentes entram em `unresolved` e reduzem confiança, nunca
  segurança.
- `criticality` vem só de attrs declarados (`criticality`, `tier`,
  `tier0..3`); tecnologia não infere criticalidade de negócio (§131).
- Recomendação sem evidência é recusada pelo contrato (`refused[]`).

## Nunca

- Aplicar patch na árvore original — tudo acontece numa cópia em tmp.
- Afirmar efeito quantificado sem `benchmark_ref` (Recommendation rejeita).
- Apresentar recusa de approve/apply como erro — é o boundary desenhado.
- Deixar um agente executar `change approve|apply` — rota crítica exige
  operations-safety reviewer + verifier + gate humano (→
  platformforge-agents).
