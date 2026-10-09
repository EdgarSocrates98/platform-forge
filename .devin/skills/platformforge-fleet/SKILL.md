---
name: platformforge-fleet
description: "Inteligência de frota multi-cluster/membro do Platform Forge — Fleet/FleetMember/FleetSnapshot com cobertura first-class, 9 perguntas determinísticas, grafo organizacional (8 camadas), history windows, analytics por dimensão, otimização (oportunidade → recomendação → ChangeIntent, nunca executa), federation (inteligência cruza, autoridade nunca) e consciência de plataforma AI (GPU/MIG, unit economics com denominador). Use para 'como está a frota', riscos/custos/capacidade/drift por membro, 'onde investir', cruzar clusters, ou comparar nós federados. Não use para um único repo/artefato (→ platformforge-core) nem para mutação (→ platformforge-change)."
---

# Fleet & enterprise analytics — cobertura sempre reportada

Input: diretório de frota no shape `lab/fleets/acme` (fleet.yaml,
policies, capacity, requests, graph…). Coverage é first-class: resposta
sem cobertura declarada é inválida. Tudo read-only.

## Verbos

```bash
platformforge fleet list|status|coverage <dir>
platformforge fleet graph|risks|costs|capacity|incidents|operations|drift <dir>
platformforge fleet golden-path|policies|recommendations <dir>
platformforge fleet risks <dir> --question "<q>"     # pergunta única
platformforge fleet report <dir>                      # north-star receipt
platformforge analytics summary|metric|maturity <path>
platformforge optimize scan|list|explain|portfolio <dir>
platformforge optimize plan <rec.json> [--out f.json]  # emite ChangeIntent só
platformforge ai workloads|gpu|economics <path>
platformforge federation manifest|export|query
```

## Disciplina

- `planned ≠ observed`; drift mostra os dois estados.
- Otimização produz `ChangeIntent` — nunca executa; o pipeline Cycle-4
  governa (boundary §303).
- Federation troca inteligência: `export` nega secrets/restricted em toda
  classificação; credenciais e execução nunca cruzam.
- AI unit economics exige denominador real — sem, é recusa.
- DX metrics são team-level only; nunca individuais.
- History windows são estritos (24h/7d/30d/90d) — dados stale não semeiam
  padrão.
- Contexto de frota é bounded: fanout por membro, nunca dump integral
  (→ platformforge-agents para o policy de contexto).
