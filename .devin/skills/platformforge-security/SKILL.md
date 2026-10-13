---
name: platformforge-security
description: "Análise defensiva de plataforma — grafo IAM (principais, ações, recursos, wildcard, trust/SCP/boundary/OIDC/role chaining), secrets com redação automática, SBOM/SLSA e supply chain, Kyverno version-aware, Cosign (claimed ≠ verified), regras PF-SEC-*/PF-IAM-* e grafo de identidade (identity-become/access/workloads/blast). Use para auditar postura, 'isto vaza segredo?', revisar políticas IAM, verificar assinatura/SLSA de artefatos, supply chain de imagens. Não cria exploits nem coleta credenciais."
---

# DevSecOps — leitura, nunca mutação

## Verbos

```bash
platformforge analyze iam <dir|policy.json>   # grafo principal→ação→recurso
platformforge analyze secrets <dir>           # valores redatados por padrão
platformforge analyze sbom <sbom.json>        # licenças, pinagem, SLSA
platformforge analyze supply <provenance.json>
platformforge analyze kyverno <dir> --kyverno-version <v>  # deprecations
platformforge analyze cosign <artifact>       # assinatura: claimed ≠ verified
platformforge analyze slsa <provenance.json>
platformforge security <root>                 # bundle secrets+iam+sbom+supply → judge
platformforge graph identity-become --node <id>   # quem pode virar o principal
platformforge graph identity-access --node <id>   # acesso por caminho de identidade
platformforge graph identity-workloads --node <id>
platformforge graph identity-blast --node <id>
```

Wildcard normalizado: `"*"` vira `wildcard` / `wildcard-principal` antes de
contar — `{"Principal":{"AWS":"*"}}` conta como público.
Admin: `"*"` ou `iam:*` em actions, ou `iam:PassRole` + `"*"` em resources.

## Disciplina

- Secrets em fact.attrs carregam só `redacted`/`sha256_prefix` — nunca
  valor. Não remover a redação pra "mostrar o contexto".
- Finding inclui `location` do artefato — remediação aponta o arquivo, não
  o valor.
- Supply chain sem assinatura verificada = finding; scanner local offline
  falhando degrada a evidência, não cancela o relatório.
- "Sem caminho de identidade encontrado" é um resultado nomeado — nunca
  apresente como "sem risco".
