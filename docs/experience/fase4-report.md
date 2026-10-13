# FASE 4 — Platform Forge: relatório de validação

Escopo (`prompt_evo_foco1.md` FASE 4): especializações (Terraform,
Kubernetes, GitOps, CI/CD, IAM, Security, SRE, Observability, FinOps,
Graphfy, Blast Radius, Policies, Agents), agent-first seguro, TUI,
graph, docs — gates sem falhas críticas e sem mutações não autorizadas.

## O que mudou (funcional)

| Mudança | Commit | Evidência |
|---|---|---|
| `platformforge hosts [all|<h>] [--launch]` — observe+launch de hosts de IA (paridade com `sf ai`/`sfa ai`/`apiforge ai`) | FE-004 | `tests/test_hosts_flow.py` 8/8; recibo real: claude/devin READY |
| `platformforge_hosts` MCP read-only | mesmo batch | `mcp tools` → 39 capabilities; handshake real PASS |
| `policy check`/`finops <verb>` sem arquivo → recusas nomeadas (`PF-POLICY-NO-FACTS`, `PF-FINOPS-NO-INPUT`, exit 2 + unlock) em vez de `PermissionError` | mesmo batch | `tests/test_missing_input_refusals.py` 5/5 |
| TUI: menu com argv inválido (`analyze`, `agents` bare) corrigido + 7 exploradores (infra, evidência, impacto, risco, agents, hosts, MCP) | `3fde172` | `test_menu_argv_parses_against_real_parser` |
| `install mcp-verify` PASS saía com exit 1 (status não normalizado) — mesma classe do bug do Azure | `c4e260e` | scratch real: `mcp-verify` rc=0 |
| `freeze manifest`/`write_manifest` crash cp1252 no Windows (`→`) | mesmo batch | manifest regenera limpo |
| Lint repo-wide zerado (ISC004/PLW1510/BLE001/B017/F541/RUF100/FURB167/I001) | `3cc6cb8` | `ruff check .` — 0 erros |
| Recibo de validação economy re-selado no HEAD (fixpoint dos gates) | `f4057cc` | `test_economy_closure` 33/33 |

## Especializações — validação por verbo real

| Domínio | Verbo exercitado | Resultado |
|---|---|---|
| Terraform/IaC | `analyze iac` no scratch (S3 + IAM `*:*`) | 2 facts; `judge` → `PF-IAC-003` violated |
| Kubernetes | `analyze k8s` | 130 docs→facts no repo; evals k8s 3/3 golden |
| GitOps/CI/CD | `analyze gha` | 1 workflow→facts |
| IAM/Security | `security`/`analyze iam` + `graph identity-*` | catálogo PF-SEC-*/PF-IAM-* no evals |
| SRE/Observability | `observe slo`, `reliability` | contratos SLO avaliados; evals 93/93 |
| FinOps | `finops costs/allocate/report` + recusa sem input | `PF-FINOPS-NO-INPUT` + unlock |
| Graphfy | `graph build/stats/blast/view/ui` no grafo real do scratch | 2 nós, hash, descriptor `available_layers` |
| Blast Radius | `graph blast --node`, `impact` | traversal com provenance |
| Policies | `policy check/list` | recusa nomeada sem facts |
| Agents | `agents list` | 41 agentes canônicos no projeto instalado |

## E2E real (projeto scratch instalado)

```text
install apply --repo scratch → forge/InstallReceipt/v1, verification PASS
install status → healthy (checks pf:*)
install mcp-verify → PASS, 39 tools, invoke platformforge_inspect ok
integrate --host devin → .devin/mcp_config.local.json; devin mcp list mostra platformforge
hosts → claude/devin/codex READY (integration healthy); copilot NOT_DETECTED honesto
analyze iac → judge → graph build → graph stats → graph view
```

## Gates

| Gate | Resultado |
|---|---|
| `pytest -q` (integral) | run 1: 2 falhas (`test_economy_closure`, `validated_sha` preso a HEAD antigo → re-selo `f4057cc`); run 2 no HEAD final: **1025 pass, 0 falhas** (`pf-suite3.xml` junit) |
| `ruff check .` | 0 erros (antes: 19 pré-existentes, corrigidos) |
| `pytest tests/test_docs_drift.py` + `test_doc_manifest.py` | verde; `CLI-SURFACE.md`/`commands.md` regenerados |
| `platformforge lab run-all` | 44/44 cenários, 0 falhas |
| `platformforge evals run` | 93/93, 0 unresolved |
| `freeze check` | `verdict: pass` após FE-004 + re-baseline |

## Mutações e fronteiras

- Nenhum `apply`/`deploy`/mutação de produção executado — core continua
  read-only; launch de host exige TTY + flag explícita e nunca roda
  com host deslogado (`login_required`, `no_tty`, `host_absent`).
- MCP `platformforge_hosts` é read-only — launch fica CLI+TTY.
- Recusas preservam `PF-*` + `unlock` (contrato mantido e reforçado
  nos dois crashes corrigidos).

## Documentação

- 12 receitas PT-BR em `docs/learn/recipes/` (terraform, kubernetes,
  cicd, impacto-blast, seguranca, sre, custos, usar-agents, usar-skills,
  verificar-mcp, graph-studio, hosts) + índice `docs/learn/README.md`.
- `CAPABILITIES.md` ganhou `platform.hosts`; `command-rationale.json`
  documenta por que/quando usar `hosts`.
- `docs/freeze/exceptions/FE-004.json` + README/manifest atualizados.

## Limitações declaradas

- `hosts` mede auth pelo status subcommand documentado de cada host;
  Copilot não tem um — `logged_in` fica `None` (desconhecido honesto).
- `integrate`/`mcp serve` assumem `platformforge` importável pelo
  `python` do ambiente — instalação via pacote (uv/pipx) é o caminho
  suportado; sessão por checkout exige o venv no PATH.
- `graph view`/`graph stats` deixam node `id: null` quando o fact não
  carrega id próprio — a aresta carrega o id composto; anotado para a
  varredura semântica da FASE 8.
- O smoke da suíte é medido por `--junitxml` (redireção de stdout do
  Windows perde a linha de contagem final sob kill).
