---
name: platformforge-sre
description: "Avalia confiabilidade de plataforma a partir de contratos SLO, eventos e sinais de observabilidade — error budget, burn rate, incident readiness, capacity headroom, correlação OTel trace→log→métrica. Use para 'este SLO aguenta', burn rate, error budget, readiness operacional, revisar alertas, planejar runbook, capacity, ou correlacionar telemetria sem credencial. Não use para custos (→ platformforge-finops) nem para blast radius estrutural (→ platformforge-graph)."
---

# SRE / observabilidade

OTel é o contrato canônico; projeções de vendor (Datadog/CloudWatch) são
leitura, nunca fonte de verdade. Tudo offline — sem credencial.

## Verbos

```bash
platformforge observe slo contract.yaml --sli '{"total_events":1e6,"bad_events":400}'
platformforge observe otel <otel.yaml>          # correlação declarada vs ausente
platformforge observe incident <signal.yaml> --alerts a.yaml --changes c.yaml
platformforge observe capacity <cap.yaml> --window 86400
```

Contrato SLO: `contracts/slo-contract.schema.json`. Regras PF-OBS-* em
`rules/catalog/sre.yaml`.

## Disciplina

- Error budget calculado do contrato + SLI observado; sem SLI →
  `PF-OBS-NODATA`, não chute.
- Correlação OTel é declarada-vs-ausente: atributo de log referenciando
  trace sem binding é finding, não prova.
- `observe incident` sem `--alerts`/`--changes` degrada a evidência — o
  sinal ausente volta em `unresolved`, não vira pressuposto.
