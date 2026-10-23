# FORGE_CONTEXT_FINAL_HOMOLOGATION — platform-forge

Relatório final do programa Install 2.0 (spec-fonte
`prompt_evo_install2.0.md` §12.6), cobrindo os ciclos 2–7 executados sobre a
baseline `docs/audits/FORGE_CONTEXT_BASELINE.md` (ciclo 1, lf-0034).
Documento de evidência: cada afirmação cita commit/PR, arquivo:linha ou
comando executado. O que não foi executado está marcado **NÃO EXECUTADO**
(§16 — nenhum teste não executado é reportado como sucesso).

## Metadados

| Campo | Valor | Evidência |
|---|---|---|
| Repo | `/home/edgar/Documentos/projetos/forjas/platform-forge` | — |
| SHA antes | `b58dc9c8460ecb14de2727970b4f941f1cf83237` | tag `v0.1.6` (2026-10-21), mesma HEAD do baseline |
| SHA depois | `6a097accebd289bab2adc17976fc6fce52023c31` | `git log -1` em `main` |
| Versão | `platformforge` 0.1.6 → **0.2.0** | `pyproject.toml` (bump em worktree, **pendente de publicação** — §10) |
| Python | `>=3.10` | `pyproject.toml` |
| CLI | `platformforge`, `platformforge-mcp` | `[project.scripts]` |
| Data | 2026-10-22 | — |

---

## 1. SHAs antes/depois

| | SHA | Descrição |
|---|---|---|
| Tag base / baseline | `b58dc9c8460ecb14de2727970b4f941f1cf83237` | `chore: rebind economy validation receipt to 0.1.6 release commit` |
| HEAD final | `6a097accebd289bab2adc17976fc6fce52023c31` | `chore(economy): rebind receipt pós-merge #87 (#88)` |

Range medido: `git log v0.1.6..HEAD` → **25 commits**, `git diff --stat` →
**28 arquivos, +6.933/−572 linhas**.

## 2. PRs

Todos os PRs mergeados em `EdgarSocrates98/platform-forge`, verdes no CI
no momento do merge.

| PR | Merge / squash | Conteúdo |
|---|---|---|
| #71 | `7663569` (merge), `abf128b` | docs(audit): FORGE_CONTEXT_BASELINE (lf-0034) |
| #72 | `535e2a6` (merge), `3c1c183` | feat(context): `forge/context/v1` — vendored registry + install wiring (ciclo 2) |
| #73 | `e7e1875` (merge), `bc92d86` | fix(build): `.gitignore` `.tokensave` + local mcp config — **sdist leak** (P1-4 do baseline) |
| #74 | `80cbfc7` (merge), `d9c1ca8` | feat(context): consumer-docs + **`.mcp.json` managed key** — install registra MCP via `kit.mcp_set` (ciclo 3, lf-0036; P0-1/P0-2 do baseline) |
| #75 | `9b4590f` (merge), `b96e8f3` `12c3684` `165b400` | feat(install): wheel distribution parity + wheel isolation test (lf-0039 §8); discovery lf-0037 (verbs §6.2); fix §8.2 leitor `data/forge*.json` |
| #76 | `e057524` (squash) | fix(lint): PLW1510/RUF100/ISC004 no wheel isolation test |
| #77 | `2102d72` (squash) | chore(receipt): re-bind economy receipt pós-#76 |
| #78 | `85a1098` (squash) | chore(docs): regen `CLI-SURFACE.md` pós lf-0037 |
| #79 | `c44884a` (squash) | fix(installkit): `_forgecontext` v1.2.1 — `timezone.utc` p/ Python 3.10 |
| #80 | `342dfe9` (squash) | chore(receipt): re-bind economy receipt pós-#79 |
| #81 | `470999b` (squash) | feat(evals): install-2.0 ciclo 5 (lf-0038) |
| #82 | `27310f1` (squash) | chore(receipt): re-bind economy receipt pós-#81 |
| #83 | `2f73232` (squash) | fix(docs): refs a `factory/runs` gitignored |
| #84 | `7857dc4` (squash) | fix(docs): refs a `graphify-out` + receipt re-bind |
| #85 | `8dcfa67` (squash) | feat(install): transactional context registry — vendored `_forgecontext` v1.3.0 (lf-0040, ciclo 7) |
| #86 | `96016ee` (squash) | chore(economy): rebind receipt pós-#85 |
| #87 | `45c95cb` (squash) | fix(install): installkit 1.0.1 — stale-lock + bootstrap security backports |
| #88 | `6a097ac` (squash) | chore(economy): rebind receipt pós-#87 |

Os rebinds de `docs/economy-parity/VALIDATION-RECEIPT.json` são mecânicos:
o receipt é pinado ao HEAD tip e precisa ser re-assinado a cada merge.

## 3. Commits

25 commits no range (`git log v0.1.6..HEAD --format='%h %s'`, ordem cronológica):

```text
abf128b docs(audit): FORGE_CONTEXT_BASELINE — install-context baseline (lf-0034 cycle 1)
7663569 Merge pull request #71 (audit/install-context)
3c1c183 feat(context): forge/context/v1 — vendored registry + install wiring (ciclo 2)
535e2a6 Merge pull request #72 (cycle/install-context)
bc92d86 fix(build): gitignore .tokensave + local mcp config — sdist leak
e7e1875 Merge pull request #73 (fix/sdist-tokensave-leak)
d9c1ca8 feat(context): consumer-docs + .mcp.json managed key — install-2.0 ciclo 3 (lf-0036)
80cbfc7 Merge pull request #74 (cycle/install-context-docs)
b96e8f3 feat(install): wheel distribution parity — forge manifests packaged + wheel isolation test (lf-0039 §8)
12c3684 discovery: lf-0037 install-time §6.2 retrieval verbs for platform-forge
165b400 fix(install): manifest reader resolve data/forge*.json packaged sob wheel (lf-0039 §8.2)
9b4590f Merge pull request #75 (cycle/install-context)
e057524 fix(lint): PLW1510/RUF100/ISC004 no wheel isolation test (#76)
2102d72 chore(receipt): re-bind economy receipt to e057524 (post-#76 tip) (#77)
85a1098 chore(docs): regen CLI-SURFACE.md pós lf-0037 (#78)
c44884a fix(installkit): _forgecontext v1.2.1 — timezone.utc p/ Python 3.10 (#79)
342dfe9 chore(receipt): re-bind economy receipt to c44884a (post-#79 tip) (#80)
470999b feat(evals): install-2.0 ciclo 5 (lf-0038) (#81)
27310f1 chore(receipt): re-bind economy receipt to 470999b (post-#81 tip) (#82)
2f73232 fix(docs): refs a factory/runs gitignored (#83)
7857dc4 fix(docs): refs a graphify-out + receipt re-bind (#84)
8dcfa67 feat(install): transactional context registry — vendored _forgecontext v1.3.0 (lf-0040) (#85)
96016ee chore(economy): rebind receipt pós-merge #85 (8dcfa67) (#86)
45c95cb fix(install): installkit 1.0.1 — stale-lock + bootstrap security backports (#87)
6a097ac chore(economy): rebind receipt pós-merge #87 (#88)
```

## 4. Arquivos modificados

`git diff --name-only v0.1.6..HEAD` → 28 arquivos. Agrupados:

| Grupo | Arquivos |
|---|---|
| Vendored | `platformforge/_forgecontext.py` (novo, v1.3.1, `_SOURCE_SHA256 = "e72e93eab21ade74"`), `platformforge/_installkit.py` (v1.0.1, `4c446922f5e77a0c`), `scripts/forge_installkit.py`, `scripts/forge_bootstrap.py` (v1.1.1) |
| Wiring de produção | `platformforge/install/service.py` (`install_transaction`/`uninstall_transaction`/`repair_context`/`repair_docs` em `:766`/`:801`/`:346`/`:365`, `_register_context`, `_unregister_context`, `_mcp_set_project`), `platformforge/discovery_ops.py` + `platformforge/discovery.py` (novos — fonte única §6.2), `platformforge/cli/main.py` (verbos `capabilities`, `policy search|get`, `knowledge search|get`, `context pack --domain`, `evals --classified`), `platformforge/mcp/parity.py` (`SERVER_CMD` → console script `platformforge-mcp`, dedupe TOML codex, `PF-MCP-CONFIG-INVALID`) |
| Empacotamento | `pyproject.toml` (force-include `forge.json`/`forge.agentic.json` → `platformforge/data/`), `.gitignore` (`.tokensave/` commitado — fix do leak) |
| Docs | `docs/audits/FORGE_CONTEXT_BASELINE.md`, `docs/install/DISTRIBUTION_PARITY.md`, `docs/evals-taxonomy.md`, `docs/CLI-SURFACE.md`, `docs/INDEX.md`, `docs/knowledge-program/*` (3 artefatos), `docs/economy-parity/VALIDATION-RECEIPT.json` (rebinds) |
| Testes | `tests/test_install_lifecycle.py` (31 testes), `tests/test_wheel_isolation.py`, `tests/test_evals_surface.py` (21), `tests/test_discovery_ops.py` (4), `tests/test_artifact_contents.py`, `tests/test_mcp.py` (+45 linhas) |

## 5. Gaps corrigidos

Mapeamento gap do baseline (§5) → correção entregue:

| Gap baseline | Status | Evidência |
|---|---|---|
| **P0-1** — nenhuma instrução de entrada chega ao consumidor (sem AGENTS.md, marker, protocolo) | **CORRIGIDO** | consumer-docs do `_forgecontext.py`: blocos `forge:ecosystem`/`forge:platform-forge` em AGENTS.md/CLAUDE.md + `AGENT_PROTOCOL.md` consolidado; `_register_context` (`service.py:750-790`); commit `d9c1ca8` |
| **P0-2** — MCP não registrado pelo install; caminho manual gravava `"command": "python"` quebrado e fora do ledger; TOML codex duplicado | **CORRIGIDO** | `.mcp.json` ganha managed key `mcpServers.platformforge` via `kit.mcp_set`/`mcp_unset` (tracking `_forge_managed`, ledger-coberto); `mcp/parity.py` `SERVER_CMD` vira o console script `platformforge-mcp`; dedupe do table TOML no codex; JSON inválido → recusa `PF-MCP-CONFIG-INVALID`; commit `d9c1ca8` + `tests/test_mcp.py` (+45) |
| — registry de contexto no workspace | **CORRIGIDO** | `.forge/context/registry.json` + `capabilities/platform-forge.json` + `ROUTING.md` sob lock único transacional (`service.py:766`); commits `3c1c183`, `8dcfa67` |
| **P1-4** — sdist local vaza `.tokensave/` (404 MB) | **CORRIGIDO** | `.tokensave/` commitado no `.gitignore`; commit `bc92d86` (PR #73) |
| — `forge.json`/`forge.agentic.json` fora do wheel (P2-4) | **CORRIGIDO** | force-include → `platformforge/data/` (`pyproject.toml:69-70`); leitor `_PKG_DIR`-aware (`service.py` — `165b400`); commits `b96e8f3`, `165b400` |
| — sem verbos §6.2 de retrieval | **CORRIGIDO** | `discovery.py`/`discovery_ops.py`: `capabilities`, `policy search|get`, `knowledge search|get`, `context pack --domain` — com proveniência sha256 e paginação; commit `12c3684` |
| — evals sem classificação §7 | **CORRIGIDO** | `evals/taxonomy.py` + `evals/surface.py` + `evals list --classified|describe|run|result`; commit `470999b` |
| — `_forgecontext` incompatível com py3.10 | **CORRIGIDO** | v1.2.1 `timezone.utc`; commit `c44884a` |
| — installkit 1.0.0 / bootstrap 1.1.0 | **CORRIGIDO** | `_installkit.py` v1.0.1 + `forge_bootstrap.py` v1.1.1 byte-idênticos ao canônico; commit `45c95cb` |

## 6. Gaps restantes

- **E2E real de hosts (§10.2) — NÃO EXECUTADO** (ciclo 8 pendente; ver §9).
- **Economia/observabilidade (ciclo 9, §11) — pendente.**
- **Publicação PyPI — pendente** (§10).
- **P0-3** — registry global `~/.forge/installations/` continua
  bootstrap-owned: `install/service.py` **lê** `installations_dir()` só em
  `update` (`:447`) e nunca chama `kit.register_installation` no install —
  instalação por wheel segue invisível ao registry de conta (verificado:
  `grep register_installation platformforge/install/service.py` → vazio).
- **P1-1** — `forge manifest` continua degradando fora de checkout:
  `--repo` default `"."` (`cli/main.py:227`) → `capability_manifest(".")`
  lê `./rules/catalog`; `forge/manifest.py` **não mudou** no range
  (`git log` vazio). O fallback `data_path()` existe mas não é usado com
  o default.
- **P1-2** — `repair` de assets managed segue restore-only para missing
  (`service.py:297`); `repair_context`/`repair_docs` agora cobrem
  `.forge/context` + docs (`:346`,`:365`) — cobertura parcial da
  divergência, assets managed drifted continuam `kept`.
- **P1-3** — perfil do contrato continua validado-mas-ignorado:
  `native profile is always "agentic"` (`service.py:155`); o recibo
  registra o perfil pedido honestamente.
- **P1-5** — quatro cópias de skills sem gerador/gate de drift — não
  tocado no range.
- **P1-6** — `forge collect` espera `capability manifest` na api-forge —
  o contrato `forge/context/v1` agora dá o caminho de descoberta, mas a
  tabela `KNOWN_FORGES` em si não mudou no range (verificar integração).
- **P2-1…P2-6** — codex MCP config, auto-reparo do update, purge de
  `.platformforge/{materials,receipts}`, `mcp serve` banner,
  `AGENTIC-OS.md` consumidor — não tocados (P2-4 corrigido, ver §5).
- **Escopo user**: `_register_context` retorna cedo (`service.py:755-757`)
  — `.forge/context` não se escreve em `$HOME` por decisão (contexto é de
  workspace, não de conta); documentado no código.
- **`DISTRIBUTION_PARITY.md`** descreve a lacuna do leitor pré-§8.2 como
  "tracked" — o §8.2 (`165b400`) corrigiu; o doc registra o histórico.
- **`mcp-handshake` BLOCKED sem o extra `mcp`** — estado de dependência
  honesto, documentado; segue o comportamento.

## 7. Testes executados

| Suíte | Arquivo | Contagem | Resultado |
|---|---|---|---|
| install lifecycle + context txn | `tests/test_install_lifecycle.py` | 31 | verde |
| wheel isolation (lf-0039) | `tests/test_wheel_isolation.py` | 1 (e2e) | verde |
| evals §7 surface | `tests/test_evals_surface.py` | 21 | verde |
| discovery ops §6.2 | `tests/test_discovery_ops.py` | 4 | verde |
| MCP parity/managed key | `tests/test_mcp.py` | +45 linhas no range | verde |
| artifact contents | `tests/test_artifact_contents.py` | — | verde |

Cross-forge (rodado em the-forge, cobrindo esta wheel): **120/120**
permutações de ordem de instalação (`test_multi_forge_e2e.py`, marker
`slow`) e `vendor.py --check` **CLEAN**.

## 8. Resultados

- `platformforge/_forgecontext.py` **byte-idêntico** ao canônico e às 4
  outras forjas (sha256 `390f5e0e61ab80dc…`, `_SOURCE_SHA256 =
  "e72e93eab21ade74"`, v1.3.1).
- `install apply` escreve `.forge/context/{registry.json,
  capabilities/platform-forge.json, ROUTING.md}` + consumer-docs +
  `.mcp.json` managed key sob um único lock transacional
  (`service.py:766`); `install uninstall` idem (`:801`); `repair`
  re-converge contexto e docs (`:346`,`:365`).
- MCP agora registrado pelo install (managed key, ledger-coberto) com o
  console script real `platformforge-mcp` — o caminho documentado sobe
  o servidor.
- `discovery.py`/`discovery_ops.py` são fonte única do mapa §6.2 → verbos
  reais; `domains` publicados: `platform-engineering,
  infrastructure-as-code, kubernetes, crossplane, terraform, finops, sre,
  supply-chain`.
- Evals classificados §7.1 servidos por `evals list --classified` +
  `describe|run|result`.
- `forge.json`/`forge.agentic.json` empacotados em `platformforge/data/`;
  leitor `_PKG_DIR`-aware (§8.2).
- Economy receipts re-pinados a cada merge (`VALIDATION-RECEIPT.json`).

## 9. Evidências Devin/Claude/Codex

**NÃO EXECUTADO.** A prova E2E real por host (§10.2 — Devin CLI, Claude
Code, Codex CLI, Copilot) pertence ao ciclo 8, pendente. Os artefatos
instalados foram verificados por testes de integração e wheel isolation
— não por telemetria de host real.

## 10. Matriz PyPI

| Componente | Estado |
|---|---|
| Wheel local (HEAD) | construída e testada em venv limpa fora do checkout (`tests/test_wheel_isolation.py`); usada na matriz 5! do the-forge |
| `forge.json`/`forge.agentic.json` no wheel | presentes em `platformforge/data/` (force-include `pyproject.toml:69-70`) |
| `data/{rules,knowledge,contracts,evals,lab,portable_skills}` | empacotados (ver `docs/install/DISTRIBUTION_PARITY.md`) |
| Publicação no índice | **PENDENTE DE PUBLICAÇÃO** — worktree marca `0.2.0`; PyPI ainda serve `0.1.6` |
| sdist | `.tokensave/` excluído via `.gitignore` (#73) |
| PyPI 0.1.6 publicado | bit-idêntico ao wheel 0.1.6 local (baseline) |

## 11. Compatibilidade

- Contratos `forge/*` v1 estáveis; `forge/context/v1` +
  `forge/context-registry/v1` adicionados sem quebrar
  `forge/InstallationManifest/v1`.
- Engine vendored compatível com py3.10 (v1.2.1) — o piso desta forja.
- Escopo user não recebe `.forge/context` por decisão
  (`service.py:755-757`); scope project/workspace cobertos.
- Rollback: uninstall transacional só remove o próprio manifesto/entry/
  blocks; `FORGE-CONTEXT-OWNERSHIP` impede deleção cruzada.

## 12. Segurança

Herdada do motor vendored + wiring local:

- `_txn_restore` com validação de path (`..`, absoluto, `\`, drive;
  blob `^\d{1,8}$`) — `_forgecontext.py:2495-2531`.
- KeyboardInterrupt/SystemExit propagam bare após rollback (`:2670+`).
- `forge_bootstrap.py` 1.1.1: `_URL_USERINFO_RE` `[^/\s]+@` (userinfo com
  `@` interno não vaza), argv trim, smoke vazio≠PASS.
- installkit 1.0.1: stale-lock `created_at` fallback para PID indecidível
  (Windows/PermissionError).
- `.mcp.json` managed key com tracking `_forge_managed`; JSON inválido
  vira recusa `PF-MCP-CONFIG-INVALID`; codex TOML com dedupe.
- `.tokensave/` não vaza mais no sdist (#73).
- Ownership `FORGE-CONTEXT-OWNERSHIP`; markers ambíguos →
  `FORGE-CONTEXT-CONFLICT`; conteúdo de usuário byte-preservado.

## 13. Performance

- Reinstall inalterado = zero writes (registry determinístico — prova na
  matriz 5!).
- `discovery_ops` é tabela em memória (fonte única).
- Economy receipts continuam pinados por commit (`VALIDATION-RECEIPT.json`
  rebinds #77/#80/#82/#84/#86/#88) — medida de integridade, não de
  economia de contexto; ciclo 9 (§11) não executado, sem claims.

## 14. Recomendações

1. Ciclo 8 (§10.2) — prova real Devin/Claude/Codex com esta wheel
   instalada; sem ela o aceite §16 sobre hosts fica aberto.
2. Publicar `0.2.0` (§12.5) ou marcar release bloqueada — nunca simular.
3. Registrar no install o `forge/InstallationManifest/v1` de conta
   (P0-3) ou documentar formalmente por que só o bootstrap escreve.
4. `forge manifest` fora de checkout: `data_path()` fallback quando o
   `--repo` não tem catálogo (P1-1) — a peça (`resources.data_path`) já
   existe; falta ligar.
5. Decidir `repair` de assets managed drifted (P1-2) e mapear perfis
   para subconjuntos reais ou recusar perfis não-implementados (P1-3).
6. Gerador único + gate de drift para as 4 cópias de skills (P1-5);
   `forge collect` por capacidade descoberta (P1-6).

## 15. Status por Forge

| Forge | `forge/context/v1` | `_forgecontext` | `_installkit` | `forge_bootstrap` | Status |
|---|---|---|---|---|---|
| the-forge | registry + docs + txn | v1.3.1 | v1.0.1 | v1.1.1 | **merged, pendente de release** (0.6.0) |
| spark-forge-aws | registry + docs + txn | v1.3.1 | v1.0.1 | v1.1.1 | **merged, pendente de release** (0.6.0) |
| spark-forge-azure | registry + docs + txn | v1.3.1 | v1.0.1 | v1.1.1 | **merged, pendente de release** (0.2.0) |
| api-forge | registry + docs + txn | v1.3.1 | v1.0.1 | v1.1.1 | **merged, pendente de release** (0.2.0) |
| **platform-forge** | registry + docs + txn | v1.3.1 | v1.0.1 | v1.1.1 | **merged, pendente de release** (0.2.0) |
| forge-doctor-api | — | ausente | v1.0.1 | v1.1.1 | **installkit only (boundary)** |
| forge-doctor-data | — | ausente | v1.0.1 | v1.1.1 | **installkit only (boundary)**; certifi PYSEC-2026-4320 |
| data-sentinel-forge | — | ausente | v1.0.0 | ausente | **deferred by owner** |

---

## Apêndice — comandos executados para este relatório

```text
git log v0.1.6..HEAD --format='%h %H %s'        → 25 commits
git diff --stat v0.1.6..HEAD                    → 28 files, +6933/−572
sha256sum platformforge/_forgecontext.py        → 390f5e0e61ab80dc…
sha256sum platformforge/_installkit.py          → 1484135ae71c396e…
sha256sum scripts/forge_bootstrap.py            → 978862ebedb9ecfb…
grep _FORGECONTEXT_VERSION platformforge/_forgecontext.py → "1.3.1"
grep register_installation platformforge/install/service.py → (vazio — P0-3 aberto)
grep -c 'def test_' tests/test_{install_lifecycle,wheel_isolation,
  evals_surface,discovery_ops}.py               → 31/1/21/4
```

## Pós-release — evidência de publicação (2026-10-23 UTC)

| Item | Estado | Evidência |
|---|---|---|
| Tag | CRIADA | `v0.2.0` no merge commit da release PR |
| GitHub Release | CRIADO | `gh release view v0.2.0` |
| PyPI | PUBLICADO | `pypi.org/pypi/platformforge/json` → `0.2.0` |
| Wheel smoke (venv limpo) | PASS | `pip install platformforge==0.2.0` + `platformforge --version` → `0.2.0` |

Notas: installkit canônico 1.0.2 (`_SOURCE_SHA256 a15ca78bb34a0109`), bootstrap 1.1.1 — propagados aos 7 carriers; `vendor.py --check` CLEAN ×7. `data-sentinel-forge`: **deferido pelo dono** (outro CLI evoluindo).

## Pós-release hotfix — evidência de publicação patch (2026-10-23 UTC)

Patch motivado pelo review: `UnicodeDecodeError` não-tipado em docs de
consumidor não-UTF-8 quebrava install **e** uninstall.

| Item | Estado | Evidência |
|---|---|---|
| Tag | CRIADA | `v0.2.1` |
| GitHub Release | CRIADO | `gh release view v0.2.1` |
| PyPI | PUBLICADO | `pypi.org/pypi/platformforge/json` → `0.2.1` |
| Wheel smoke | PASS | wheel publicado contém `_forgecontext` v1.3.2 (`_read_doc` presente) — verificado via `pip download platformforge==0.2.1` |
| Regressão | PASS | teste cp1252 `AGENTS.md` → `FORGE-CONTEXT-CONFLICT` nomeado em install e uninstall |

## Pós-release hardening waves — evidência (2026-10-23 UTC)

Duas ondas de patch: `0.2.2` (install 2.0 hardening — traversal containment, lock token, journal quarantine, repair schema, atomic-write mode) e `0.2.3` (receipt truthfulness, user-scope no-op, unsafe drift surfacing).

| Item | Estado | Evidência |
|---|---|---|
| Tags | CRIADAS | `v0.2.2`, `v0.2.3` nos merge commits |
| GitHub Release | CRIADO | `gh release view v0.2.3` |
| PyPI | PUBLICADO | `pypi.org/pypi/platformforge/json` → `0.2.3` |
| Wheel conteúdo | VERIFICADO | `pip download platformforge==0.2.3` → `_installkit` 1.0.4 (`_INSTALLKIT_VERSION`) |
| Install E2E (wheel→workspace) | PASS | ver secção Cycle 8 abaixo |

## Cycle 8 — E2E real em host Devin (EXECUTADO 2026-10-23)

Setup: venv limpa + `pip install` dos wheels PyPI publicados →
`sparkforge-aws install --root /tmp/e2e-host/proj --host devin -y` →
receipt `forge/InstallReceipt/v1` `status=completed`, `verification=PASS`.

Jornada do host (esta sessão Devin CLI), cada passo verificado por saída
de ferramenta, não por afirmação textual:

| Passo | Resultado | Evidência |
|---|---|---|
| Descobrir Forge | ✓ | bloco managed `forge:ecosystem` em `AGENTS.md` do workspace |
| Registry | ✓ | `.forge/context/registry.json` → `spark-forge-aws: available` |
| Protocolo | ✓ | `AGENT_PROTOCOL.md` (4 130 B) + `ROUTING.md` |
| Capacidades | ✓ | `sparkforge-aws capabilities` → `forge/capabilities/v1`, 0.6.3 |
| Rules | ✓ | `rules lookup --id SF-PY-001` → catálogo retorna a regra |
| Knowledge (wheel, sem git) | ✓ | `knowledge search "glue worker"` → `glue/workers-and-capacity.md`, `knowledge_origin=package` (site-packages) |
| Regra aplicada a caso real | ✓ | `analyze pyspark job.py` → `judge --glue 5.1` → finding `SF-PY-002` P1 (`df.collect()` job.py:5), evidência `f_6bba98` |
| Receipt auditável | ✓ | `.sparkforge_aws/receipts/install-*.json` |

Outros hosts: Claude Code / Codex CLI / Copilot — não instalados neste
ambiente; marcados `não verificado` (não como sucesso). A matriz de hosts
por path renderizado é coberta pelos testes de render (`rendered_hosts`).

## Cycle 9 — economia/observabilidade (medido, não estimado)

| Métrica | Observado |
|---|---|
| Bytes adicionados ao workspace | 37 897 (knowledge stubs) + 28 169 (.forge) + docs |
| `AGENTS.md` / `CLAUDE.md` / `AGENT_PROTOCOL.md` | 1 978 / 418 / 4 130 B |
| `registry.json` + `ROUTING.md` + capability manifest | 9 094 / 1 508 / 17 567 B |
| Knowledge stubs | 43 ponteiros (37 897 B); conteúdo carregado lazy do pacote |
| Host mirrors (.agents + .devin) | 1 723 209 B cada (perfis+skills renderizados) |
| Latência cold-start (spawn+exec) | capabilities ≈25 s, rules ≈15 s, knowledge ≈5 s (1ª chamada, inclui startup do intérprete) |
| Tokens de provider | `unresolved` — sem transcript de host, não estimado |

Sentinel: release `v0.2.2` existe no GitHub; publicação PyPI
**bloqueada** — workflow `Release` gated no environment `pypi`
(trusted publisher + approval humana). Job `publish to PyPI (OIDC, gated)`
falhou por design até o dono aprovar.
