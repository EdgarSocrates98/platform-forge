# Receita — auditar CI/CD (GitHub Actions e pipelines)

**O quê:** `analyze gha` lê workflows; `analyze gitops` cobre ArgoCD/Flux;
`analyze ownership` conecta CODEOWNERS ao que o pipeline toca.
**Por que:** permissões de token, actions não pinadas, secrets em workflow
e caminho de entrega respondidos com evidência.
**Quando:** revisar workflow novo, auditar supply chain do pipeline,
checar o caminho commit→deploy.
**Quando não:** rodar o pipeline — o forge analisa a definição, nunca
executa CI.

## Passo a passo

```bash
platformforge analyze gha --repo .               # .github/workflows/*
platformforge analyze gitops --repo gitops/      # Application/Flux manifests
platformforge analyze sbom --repo .              # supply chain quando houver SBOM
platformforge judge gha-facts.json               # findings com rule_id
```

## Saída esperada / interpretação

Facts por workflow (actions, triggers, permissions); findings de
supply chain citam a regra e a fonte datada do catálogo.

## Verificação

`graph build` com facts de gha + k8s mostra a cadeia commit → deploy →
workload; `graph paths --src <repo> --dst <deploy>` confirma o caminho.

## Limitações

Cobre GHA/ArgoCD/Flux declarado; pipelines Jenkins/GitLab fora do
vocabulario aparecem como undetected em `collect`, nunca droppados.

## Erros comuns

| Sintoma | Causa | Ação |
|---|---|---|
| 0 workflows | repo sem `.github/workflows` | aponte o repo certo em `--repo` |
| permissão não flagada | workflow sem `permissions:` explícito | ausência é ela mesma um sinal — veja o finding |

## Uso por agentes

`platform-gitops-specialist` lê os artifacts de entrega e responde "este
pipeline entrega o quê, para onde, com qual evidência".
