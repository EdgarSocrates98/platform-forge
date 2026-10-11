# Receita — auditar Kubernetes/Helm/Kustomize

**O quê:** `analyze k8s` lê manifests; `analyze helm`/`analyze kustomize`
cobrem templates e overlays; findings saem por `judge`/`reliability`.
**Por que:** postura de workloads, RBAC, limites e probes respondida com
evidência, offline.
**Quando:** revisar manifest/PR, medir cobertura de probes/limits, auditar
namespace.
**Quando não:** estado do cluster ao vivo — isso é `live` (host-side,
read-only) ou um dump exportado para `collect`.

## Passo a passo

```bash
platformforge analyze k8s --repo deploy/ > k8s-facts.json
platformforge analyze helm --repo charts/        # charts renderizados ou valores
platformforge analyze kustomize --repo overlays/
platformforge judge k8s-facts.json               # regras k8s + sre
platformforge reliability k8s-facts.json         # somente regras SRE/K8S
```

## Saída esperada / interpretação

Facts por documento (`kind`, `metadata.name`, atributos); findings citam
`rule_id` — ausência de finding em `reliability` não é "saudável", é
"nenhuma regra violada no que foi observado".

## Verificação

`graph build k8s-facts.json` + `graph deps --node <workload>` mostram o
que depende do workload antes de mexer nele.

## Limitações

Manifests sem `resources:`/`probes` geram findings de ausência — o tool
não inventa valores default que o cluster aplicaria.

## Erros comuns

| Sintoma | Causa | Ação |
|---|---|---|
| 0 docs | diretório sem YAML k8s | confira `kind:`/`apiVersion:` no alvo |
| finding sem evidence | bug — reporte | findings inválidos por construção não deveriam existir |

## Uso por agentes

`platform-kubernetes-specialist` faz a mesma leitura e ainda cruza com o
grafo (quem depende deste Deployment).
