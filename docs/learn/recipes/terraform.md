# Receita — auditar Terraform/IaC

**O quê:** `platformforge analyze iac` extrai facts de HCL/plan/state;
`judge` aplica o catálogo de regras `PF-IAC-*`.
**Por que:** resposta determinística sobre recursos declarados, sem rodar
`terraform plan` nem tocar cloud.
**Quando:** revisar PR de infra, auditar módulo, medir postura antes de
aplicar.
**Quando não:** mutação (`apply`/`deploy`) — fora do core; plan binário —
exporte JSON primeiro.

## Passo a passo

```bash
platformforge analyze iac --repo . > facts.json   # facts com provenance
platformforge judge facts.json                    # findings com rule_id
platformforge analyze drift --repo .              # desejado vs observado (tfstate)
platformforge analyze terraform --help            # demais leituras IaC
```

## Saída esperada / interpretação

`facts[]` são observações ancoradas (arquivo/recurso); `findings[]`
carregam `rule_id` + `evidence` — `unresolved` é resposta honesta, não
lacuna a preencher.

## Verificação

`platformforge graph build facts.json` materializa os recursos como nós;
`graph stats` confirma nós/arestas contados.

## Limitações

Cobre o que está em arquivo — recursos criados fora do Terraform só
aparecem via `analyze drift` com tfstate ou via `live` (host-side).

## Erros comuns

| Sintoma | Causa | Ação |
|---|---|---|
| 0 facts | path não contém `.tf` | aponte `--repo` para o módulo |
| `PF-POLICY-NO-FACTS` | `policy check` sem facts.json | rode `judge`/`analyze` antes |

## Uso por agentes

`platform-iac-specialist` lê os mesmos facts e responde em linguagem de
plataforma — use quando a pergunta for "o que este módulo faz de errado"
e não "liste findings".
