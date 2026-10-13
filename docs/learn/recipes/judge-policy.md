# Receita — o que as regras dizem dos facts?

**O quê:** `platformforge judge`/`policy check` aplicam o catálogo de regras
versionado sobre facts e emitem verdicts com `rule_id`.
**Por que:** findings com regra citável — governança, não opinião.
**Quando:** compliance, hardening, gates de plataforma.
**Quando não:** inventário — isso é `inspect`; enforcement — recusado no core.

## Passo a passo

```bash
platformforge policy --repo . --json
platformforge judge --help            # escopo e flags do veredito
```

## Saída esperada / interpretação

Findings com `rule_id` + evidência + `unresolved` explícito; refusal traz
`PF-*` + `unlock`. Reporte o `rule_id` — não parafraseie a regra.

## Verificação

O catálogo é versionado — o mesmo facts doc produz o mesmo verdict na mesma
versão do catálogo.

## Limitações

Regras julgam o que facts declaram; sem fact não há finding — `unresolved`
é a saída honesta, nunca um "passou".

## Erros comuns

| Sintoma | Causa | Ação |
|---|---|---|
| zero findings suspeito | facts vazios antes do judge | rode `inspect` antes |
| `PF-*` refusal | ação fora do permitido | `unlock` diz o desbloqueio seguro |

## Uso por agentes

Padrão do AGENTS.md: resposta sobre regras → `judge`/`policy check`; citar
`rule_id` é obrigatório.
