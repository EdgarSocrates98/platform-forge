# Receita — postura de segurança (secrets, IAM, supply chain)

**O quê:** `security <root>` é o bundle secrets+iam+sbom+supply;
`analyze secrets|iam|sbom|supply|kyverno|cosign|slsa` são as leituras
individuais; `graph identity-*` mede o que uma identidade vira.
**Por que:** exposição respondida com evidência ancorada e redação no
boundary — segredo nunca vaza para o output.
**Quando:** auditoria de postura, revisão de PR com IAM/policies,
"isto vaza segredo?".
**Quando não:** criar exploits ou coletar credenciais — fora de escopo
por design.

## Passo a passo

```bash
platformforge security --repo .                  # bundle completo
platformforge analyze secrets --repo .           # vazamento em arquivos
platformforge analyze iam --repo .               # políticas e trust
platformforge graph build facts.json
platformforge graph identity-blast --node <principal>  # o que a identidade alcança
```

## Saída esperada / interpretação

Findings `PF-SEC-*`/`PF-IAM-*` com evidence; wildcard `*` em Action e
Resource aparece como violação; `claimed ≠ verified` em Cosign/SLSA é
dito explicitamente.

## Verificação

`graph identity-access` e `identity-workloads` confirmam a leitura do
mesmo facts doc pelo ângulo da identidade.

## Limitações

Sem material de segredo no output — redação é no boundary; trust/SCP/
boundary cobertos no que os artifacts declaram.

## Erros comuns

| Sintoma | Causa | Ação |
|---|---|---|
| iam vazio | sem policies no path | aponte `--repo` ao dir com IAM/Terraform |
| identity-blast sem nó | principal não virou fact | `analyze iam` antes do `graph build` |

## Uso por agentes

`platform-security-specialist` analisa; `platform-security-reviewer`
revisa a conclusão de outro agente — nunca emitem material de segredo.
