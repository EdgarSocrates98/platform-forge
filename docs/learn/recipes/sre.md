# Receita — SLO, error budget e confiabilidade

**O quê:** `observe slo <contrato>` avalia SLI contra janelas;
`observe slo-burn` mede burn rate multi-window; `reliability <facts>`
roda só as regras SRE/K8S do catálogo.
**Por que:** "este SLO aguenta" vira aritmética sobre medição, não
opinião — e `unresolved` quando o denominador falta.
**Quando:** revisar contrato SLO, medir burn rate num incidente,
auditar readiness de um serviço.
**Quando não:** sem contrato/eventos medidos — o forge não inventa SLI;
causa raiz de incidente é correlação, nunca certeza (`observe incident`
diz isso).

## Passo a passo

```bash
platformforge observe slo slo.yaml                    # contrato SLO
platformforge observe slo-burn slo.yaml --windows 1h,6h,24h
platformforge observe capacity --repo .               # headroom
platformforge reliability facts.json                  # regras SRE/K8S sobre facts
platformforge diagnose incident.yaml                  # alerts+changes+graph correlacionados
```

## Saída esperada / interpretação

Error budget consumido por janela, burn rate, headroom; quando o input
não fecha a conta a resposta é `unresolved`/`unknown` — nunca zero
implícito.

## Verificação

`observe prometheus`/`grafana` projetam os mesmos sinais para os formatos
de alerta/dashboard — boa checagem cruzada do contrato.

## Limitações

Sem credencial nem query a monitoring: o forge lê contratos e dumps
exportados; coleta ao vivo é `live` (host-side, allowlist read-only).

## Erros comuns

| Sintoma | Causa | Ação |
|---|---|---|
| `unresolved` no SLO | SLI sem denominador medido | forneça o total de eventos/janela |
| slo-burn vazio | janelas sem eventos | confira o campo de tempo dos eventos |

## Uso por agentes

`platform-sre-specialist` interpreta telemetria/SLO e marca correlação
como correlação; `platform-incident-coordinator` monta a linha do tempo.
