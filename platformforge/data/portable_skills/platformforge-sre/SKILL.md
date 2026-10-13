---
name: platformforge-sre
description: "Avalia confiabilidade de plataforma a partir de contratos SLO, eventos e sinais de observabilidade — error budget, burn rate multi-window, incident readiness, capacity headroom, postmortem, DR, correlação OTel trace→log→métrica e projeções prometheus/grafana. Use para 'este SLO aguenta', burn rate, error budget, readiness operacional, revisar alertas, planejar runbook, capacity, ou correlacionar telemetria sem credencial. Não use para custos (→ platformforge-finops) nem para blast radius estrutural (→ platformforge-graph)."
---

# SRE / observabilidade

OTel é o contrato canônico; projeções de vendor (prometheus/grafana) são
leitura, nunca fonte de verdade. Tudo offline — sem credencial.

## Verbos

```bash
platformforge observe slo contract.yaml --sli '{"total_events":1e6,"bad_events":400}'
platformforge observe slo-burn contract.yaml --windows '{"1h":{"good":1,"bad":0,"total":100}}'
platformforge observe otel <otel.yaml>          # correlação declarada vs ausente
platformforge observe semconv <attrs.json>      # conformidade de convenção semântica
platformforge observe incident <signal.yaml> --alerts a.yaml --changes c.yaml
platformforge observe timeline <events.json>
platformforge observe postmortem --incident inc.json
platformforge observe capacity <cap.yaml> --window 86400
platformforge observe dr <dr.yaml> --facts facts.json
platformforge observe prometheus <rules.yaml>   # projeção: alertas/recording
platformforge observe grafana <dashboard.json>  # projeção: painéis/datasources
platformforge reliability <facts.json>          # sre+k8s rules only
platformforge correlate <otel.yaml>             # = observe otel
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
- Burn rate usa janelas múltiplas — `slo-burn` exige `--windows` por
  janela declarada.
