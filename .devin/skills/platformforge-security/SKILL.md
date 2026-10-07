---
name: platformforge-security
description: "Análise defensiva de plataforma — grafo IAM (principais, ações, recursos, wildcard), secrets com redação automática, SBOM/SLSA e supply chain, e regras PF-SEC-*/PF-IAM-*. Use para auditar postura, 'isto vaza segredo?', revisar políticas IAM, verificar assinatura/SLSA de artefatos, supply chain de imagens. Não cria exploits nem coleta credenciais."
---

# DevSecOps — leitura, nunca mutação

## Verbos

```bash
platformforge analyze iam <dir|policy.json>   # grafo principal→ação→recurso
platformforge analyze secrets <dir>           # valores redatados por padrão
platformforge analyze sbom <sbom.json>        # licenças, pinagem, SLSA
platformforge analyze supply <provenance.json>
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
