---
name: platformforge-lab
description: "Executa e avalia cenários determinísticos do Forge Lab — fixtures offline com contrato expected.yaml, comparação expected-vs-observed por prefixo de regra e categoria. Use para validar analyzer novo, regredir regras, criar cenário novo para um finding, ou avaliar o próprio platform-forge. Não substitui pytest (cobre comportamento unitário; Lab cobre o pipeline analyze→judge)."
---

# Forge Lab — avaliação determinística

Cenário = `lab/scenarios/<nome>/` com `fixture/` (artefatos) +
`expected.yaml` (`analyzers`, `rules_fired`, `categories`).

## Verbos

```bash
platformforge lab list                          # cenários
platformforge lab run <nome>                    # um
platformforge lab run-all                       # suite
```

## Criar cenário

1. `lab/scenarios/<nome>/fixture/` com os artefatos mínimos.
2. `expected.yaml`: `analyzers: [iac|k8s|gha|gitops|secrets|iam|slo|finops|supply|catalog|crossplane]`, `rules_fired` por prefixo (`PF-K8S-`), `categories`.
3. `lab run <nome>` — runner roda analyze+judge e compara.

Domínios por arquivo único leem um nome fixo dentro de `fixture/`:
`iam`→`policy.json`, `supply`→`supply.json`, `finops`→`costs.json`,
`slo`→`slo.yaml` + `events.yaml`. Os demais (iac, k8s, gha, gitops,
secrets, sbom, catalog, crossplane) varrem `fixture/` inteira.

## Disciplina

- `rules_fired` é prefixo — liste regra inteira se o caso depende dela.
- Cenário que passa com finding errado ainda falhou — confira `observed`.
- Fixture não contém segredo real — usar placeholder + pattern.
