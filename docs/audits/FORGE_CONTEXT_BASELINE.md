# FORGE_CONTEXT_BASELINE — platform-forge

Auditoria do Ciclo 1 (spec `lf-0034`, prompt-fonte `prompt_evo_install2.0.md` §0–§3).
Escopo: somente evidência — todo achado cita o comando que o produziu ou o
arquivo/linha que o sustenta. Nada foi preenchido por suposição.

## Metadados

| Campo | Valor | Evidência |
|---|---|---|
| Repo | `/home/edgar/Documentos/projetos/forjas/platform-forge` | — |
| HEAD | `b58dc9c8460ecb14de2727970b4f941f1cf83237` | `git log -1` |
| Versão | `0.1.6` | `pyproject.toml` (`name = "platformforge"`) |
| Python | `>=3.10` | `pyproject.toml` |
| Build | hatchling, pacote na raiz (`platformforge/`) | `[build-system]` |
| CLI | `platformforge`, `platformforge-mcp` | `[project.scripts]` |
| Wheel publicado | `platformforge-0.1.6-py3-none-any.whl` (1.348.731 B) | PyPI JSON API |
| Wheel local | **sha256 idêntico ao publicado** (`162be2b8…`) | `sha256sum` comparado |
| sdist publicado | 3.501.791 B | PyPI JSON API |
| sdist local | **83.018.615 B** — contém `.tokensave/` (404 MB) | `tar -tzvf` |

---

## 1. Inspeção de arquitetura (§3.1)

### 1.1 Mapa de módulos

Pacote `platformforge/` na raiz (não-src). Relevantes ao contexto:

| Área | Módulo | Papel |
|---|---|---|
| Install lifecycle | `install/service.py` (421 linhas) | adapter `forge/*` sobre o motor nativo + kit vendored |
| Motor de install nativo | `distribution/service.py` (225), `distribution/models.py`, `distribution/bundle.py`, `distribution/hostflow.py` | plan/apply/uninstall/upgrade/doctor com sha256 por arquivo + bundles relocáveis |
| Installkit compartilhado | `_installkit.py` (1732) | **vendored, byte-idêntico** a `the-forge/scripts/installkit` e às cópias de api-forge/data-sentinel (mesmo md5 `a31bd4f0…`) |
| CLI | `cli/main.py` (3832 linhas, argparse) + `portable_cli.py` (199) | verbos `install/uninstall/upgrade/portable/workspace/mcp/hosts/integrate/…` |
| Agents | `agents/roster.py` (41 AgentSpec) + `agents/mirrors.py` | roster canônico em código; mirrors gerados |
| Skills portáveis | `data/portable_skills/` (12 dirs: 11 `platformforge-*` + `portable_skills/` aninhado?) — ver nota | package data dentro do wheel |
| Package data | `platformforge/data/{rules,knowledge,contracts,evals,lab,portable_skills}` | force-include do wheel |
| Knowledge | `knowledge/{aws,crossplane,kubernetes,terraform}/*.yaml` + `sources.yaml` (88 K) | pacotes de conhecimento com proveniência |
| Rules | `rules/catalog/*.yaml` (9 arquivos) → 63 regras | `load_catalog` |
| Contracts | `contracts/*.schema.json` (23) | schemas JSON |
| Evals | `evals/cases/` (94 casos) + `evals/qpt-bench/` | corpus |
| Lab | `lab/{scenarios,fleets,chaos-pod-kill}` (784 K) | cenários de laboratório |
| MCP | `mcp/{server,registry,tools,parity}.py` | JSON-RPC stdio **hand-rolled** (sem dep `mcp`); 39 tools |
| Forge interop | `forge/{manifest,delegate,collect}.py` | `forge manifest|delegate|verify|discover|collect` |
| Workspace | `workspace/service.py` (`ensure_workspace`, `load_workspace`, `add_repo`, `remove_repo`, `doctor`) | `.platformforge/workspace.json` (`platformforge/workspace-manifest/v1`) |
| Recursos | `resources.py` (`data_path`, materialização via `importlib.resources`) | resolve `platformforge/data/` no wheel |
| Bootstrap | `scripts/forge_bootstrap.py`, `scripts/forge_installkit.py` | vendored, byte-idênticos a api-forge (`cmp -s` verificado) |
| UI/wizard | `ui/`, `portable_cli.run_guided_install` | wizard interativo bare `platformforge install` |

Nota sobre `data/portable_skills/`: a listagem mostra 12 entradas —
`platformforge-{agents,change,core,economy,finops,fleet,governance,graph,lab,sdd,security,sre}`
— e o render instala os SKILL.md encontrados (verificado: 12 SKILL.md por
diretório de skill no alvo — `platformforge-*` + um extra aninhado).

### 1.2 Canônico vs derivado

| Item | Status | Gerador oficial |
|---|---|---|
| `platformforge/agents/roster.py` (41 AgentSpec) | **canônico** | edição manual (`agents lint`) |
| `agents/*.md`, `.agents/agents/*.md`, `.claude/agents/*.md`, `.codex/agents/*.toml`, `.devin/agents/*.md` | derivado | `platformforge agents sync` (`agents/mirrors.py`, `TARGETS` fixo) — gate `agents check` |
| `.devin/skills/`, `.claude/skills/`, `.agents/skills/`, `platformforge/data/portable_skills/` | **ambíguo** — 4 cópias byte-idênticas (md5 verificado); `portal_adapter.py:27` chama `.devin/skills` de canônico, mas **não há gerador/gate de drift para skills** | nenhum encontrado |
| `_installkit.py`, `scripts/forge_*` | derivado (vendored) | `the-forge/scripts/installkit/` |
| `install/service.py`, `distribution/*` | **canônicos desta forja** | edição manual |
| `forge.json`, `forge.agentic.json` | **canônico** | edição manual |
| `contracts/*.schema.json` | **canônico** | edição manual |
| `.platformforge/cases|ledgers` (golden/holdout) | **canônico, rastreado em git** | edição manual (dogfooding) |
| `AGENTS.md`, `CLAUDE.md`, `AGENTIC-OS.md`, … ~60 docs de raiz | **canônico** | edição manual |

### 1.3 Host integration e MCP

- `install` → `distribution.service.portable_assets`: agents renderizados do
  roster p/ `.agents/agents` (md), `.claude/agents` (md), `.codex/agents`
  (**toml**), `.devin/agents` (md); skills → `.agents/skills`,
  `.claude/skills`, `.devin/skills`. `copilot` mapeia para `agents`
  (sem `.github/` — observado: nenhum arquivo `.github` no alvo).
- MCP: `install` escreve **apenas** `.platformforge/mcp.json` — um hint
  `platformforge/mcp-bootstrap/v1` ("scope: workspace-local"), **não**
  `.mcp.json` gerenciado. O caminho real de registro é `platformforge mcp
  integrate --host …` (`mcp/parity.py`) — fora do ledger.
- MCP server: `platformforge-mcp`/`python -m platformforge mcp serve` —
  JSON-RPC 2.0 stdio implementado à mão (`mcp/server.py`), sem dep `mcp`;
  `install mcp-verify` executa handshake real → **PASS, 39 tools** na venv
  limpa (observado).
- `platformforge hosts` — observa binários de host (claude/devin/codex/copilot
  → `NOT_DETECTED` nesta máquina); `--launch` é fronteira humana TTY.

---

## 2. Matriz de recursos (§3.2)

Evidência executada em `/tmp/pf-venv` (wheel), alvo `/tmp/pf-target` com
`git init`, `HOME=/tmp/pf-home` isolada. Sem teste com host real — células
sem prova direta marcadas `não verificado`.

| Recurso | Existe na fonte | Está no wheel | Instalado no alvo | Descoberto pelo host | Utilizável | Verificado |
|---|---|---|---|---|---|---|
| Skills | SIM — 4 árvores idênticas (`.devin/skills` chamado canônico) | SIM — `platformforge/data/portable_skills` | SIM — `.agents/skills`, `.claude/skills`, `.devin/skills` (12 SKILL.md cada; codex consome `.agents`) | convenção de diretório | SIM | SIM — escritos e contados |
| Agents | SIM — `roster.py` (41) | SIM — roster vai no pacote; render em runtime | SIM — 41 arquivos por host dir (`.agents|.claude|.devin` md; `.codex` toml) | convenção de diretório | SIM | SIM — `install --yes` → 201 assets |
| MCP | SIM — server próprio stdio | SIM — entry point `platformforge-mcp` | PARCIAL — só hint `.platformforge/mcp.json`; `.mcp.json` exige `mcp integrate` manual | **NÃO pelo install** — nenhuma config de host é escrita | SIM — handshake PASS (39 tools) | SIM — `install mcp-verify` PASS |
| Knowledge | SIM — `knowledge/` (14 packs yaml) | SIM — `data/knowledge` | **NÃO copiado** | **NÃO** — sem ponteiro no alvo | SIM — `knowledge packs` → 13 packs ok | SIM |
| Rules | SIM — `rules/catalog/` (9 yaml, 63 regras) | SIM — `data/rules/catalog/` | **NÃO copiado** | **NÃO** | PARCIAL — `judge`/`forge manifest` leem do pacote, **mas `--repo .` default desvia para cwd** (ver §5 P1-3) | SIM |
| Evals | SIM — `evals/cases/` (94) | SIM — `data/evals` (164 arquivos) | **NÃO copiado** | **NÃO** | SIM — `evals list` funciona no alvo | SIM |
| Lab | SIM — `lab/` | SIM — `data/lab` (107) | **NÃO copiado** | **NÃO** | SIM — `lab run-all` → 44/44 passed | SIM |
| Contracts/schemas | SIM — `contracts/` (23) | SIM — `data/contracts` | **NÃO copiado** | **NÃO** | SIM via runtime | SIM |
| Protocols | SIM — AGENTS.md de repo; `platformforge/agentic_runtime` interno | **NÃO** — nenhum AGENT_PROTOCOL/protocolo de consumidor no wheel | **NÃO** | **NÃO** — nem marcador existe | **NÃO** | SIM — ausência confirmada |
| Verificadores | SIM — `install doctor/status`, `portable verify`, `validate.py` gates | SIM (código) | n/a | **NÃO** | SIM | SIM — doctor executado |
| Políticas | SIM — AGENTS.md/raiz, `.devin` hooks? (repo tem só `.devin/{agents,skills}`) | **NÃO** | **NÃO** | **NÃO** | **NÃO** | SIM |
| Manifesto de capacidades | `forge.json`/`forge.agentic.json` + `forge manifest` verb + `capability list|manifest|check` | `forge.json` **não** entra no wheel; o **verbo** sim | `.platformforge/distribution-manifest.json` escrito no install (capability list interna) | PARCIAL — manifesto de distribuição existe no alvo, mas lista só 5 capabilities genéricas | SIM — `forge manifest` roda (com ressalva §5 P1-3) | SIM |
| Registry de contexto (`.forge/context/`) | **NÃO existe** | n/a | **NÃO** — `.platformforge/workspace.json` cobre workspace multi-repo, não contexto de forjas | **NÃO** | **NÃO** | SIM |
| Registry global `~/.forge/installations/` | contrato do installkit | n/a | **NÃO escrito** — `install` não chama `register_installation` (ausência confirmada em `/tmp/pf-home`) | **NÃO** | **NÃO** | SIM |

### 2.1 Evidência bruta principal

```text
$ HOME=/tmp/pf-home /tmp/pf-venv/bin/platformforge install --yes   # /tmp/pf-target
status: completed · managed_files: 51 (recibo); 201 assets no manifesto de distribuição
dirs: .agents/agents(41) .agents/skills(12) .claude/agents(41) .claude/skills(12)
      .codex/agents(41 *.toml) .devin/agents(41) .devin/skills(12)
.platformforge/: components.json distribution-manifest.json install-receipt.json
                mcp.json (hint) receipts/ workspace.json
SEM: AGENTS.md · CLAUDE.md · .mcp.json · .github/* · ~/.forge/installations/*

$ platformforge install doctor          # status: healthy — pf:* PASS + mcp-handshake PASS
$ platformforge install mcp-verify      # handshake real → 39 tools, invoke PASS
$ platformforge lab run-all             # {'failed': 0, 'passed': 44}
$ platformforge forge manifest          # rule_count: 0 + warning "catalog dir missing"
$ platformforge forge manifest --repo <site-packages>/platformforge/data   # rule_count: 63
$ platformforge portable build /tmp/pf-bundle --host agents --host claude
  → 107 assets + MANIFEST.sha256;  portable verify → valid: true
$ platformforge install uninstall --purge  → removed: 51; dirs de host podados
```

---

## 3. Análise do instalador (§3.3)

Arquitetura em duas camadas — **diferente das irmãs**:

```text
cli/main.py + portable_cli.py
  → install/service.py            (adapter forge/*: escopos, hosts, perfis,
                                   recusas FORGE-INSTALL-*, lock do kit,
                                   registry de schemas)
    → distribution/service.py     (motor nativo: plan/apply/uninstall/doctor,
                                   InstallPlan/InstallReceipt/
                                   DistributionManifest, sha256 por arquivo,
                                   write staging + os.replace)
    → _installkit.py              (só peças: resolve_scope parcial? não —
                                   SCOPES/E_*, acquire_lock, components,
                                   mcp_verify, _prune_empty_dirs, registry
                                   helpers — pouco usado)
```

| Aspecto | Implementação observada |
|---|---|
| Resolução do alvo | `install/service._resolve`: `--repo`/cwd `.resolve()`; **project exige `.git` ou `forge.json`** (senão `FORGE-INSTALL-NOT-A-REPO`); workspace = ancestral com `.platformforge/workspace.json`, senão o próprio root (diretório fresco aceito); user = `Path.home()` |
| `scope=project` | `<root>/.platformforge/` + mirrors de host na raiz |
| `scope=workspace` | idem — mesma escrita; distinção só na resolução do root |
| `scope=user` | `$HOME`: `~/.agents`, `~/.claude`, `~/.codex`, `~/.devin`, `~/.platformforge` — verificado em `/tmp/pf-home2` |
| Assets copiados | agents (roster→mirrors) + skills (`data/portable_skills`) + `.platformforge/mcp.json` hint |
| Assets referenciados | rules/knowledge/contracts/evals/lab — via `platformforge/data/` no pacote (`resources.data_path`) |
| Assets ignorados | AGENTS.md/CLAUDE.md/AGENTIC-OS.md de consumidor, `forge.json`, `docs/`, `.github` (copilot), `.mcp.json` real |
| Merge | **não há merge em arquivos do usuário** — nenhum marker block, nenhum `.mcp.json` gerenciado; escrita só em caminhos managed |
| Ownership | `install-receipt.json` (path→sha256) + `distribution-manifest.json` (distribution_id sha256 do conteúdo); arquivo modificado = conflito que **recusa o plano inteiro** (`PF-DIST-CONFLICT`) em vez de pular |
| Uninstall | remove só arquivos cujo sha256 confere com o recibo; modificados = `preserved_modified`; `--purge` remove `workspace.json`; dirs vazios podados (`kit._prune_empty_dirs`) |
| Repair | reaplica para missing; **arquivos managed modificados pelo usuário NÃO são restaurados** ("user content by contract" — `service.py:322`) — diverge do kit (kit repair re-escreve managed drifted) |
| Update | `pip install --upgrade <checkout>` na venv registrada — exige `~/.forge/installations/platform-forge.json` (escrito pelo **bootstrap**, não pelo install) |
| Host selection | `--host` append; mapa contrato→nativo: `copilot→agents`; escolhas CLI: agents/claude/codex/devin/copilot/all |
| Perfis | contrato `minimal|recommended|full` validado mas **sempre mapeado para profile nativo `agentic`** (um único conjunto de assets) |
| Componentes | `--components` gravado em `.platformforge/components.json` (inclui `execution_profile`); não filtra assets (native engine ignora asset_kinds) |
| Registry | `~/.forge/installations/` **nunca escrito pelo install** — só o `forge_bootstrap.py` registra |
| Lock | `kit.acquire_lock(.platformforge)` |
| Staging | escreve `*.platformforge-stage` + `os.replace` atômico; verificação de hash pós-stage |
| Receipts de verbos | `_write_receipt` em `cli/main.py` → `.platformforge/receipts/rcpt-*.json` por operação com `--repo` |

### 3.1 Superfície extra de distribuição

- `platformforge portable build|verify|install|doctor` — bundle relocável
  `assets/` + `manifest.json` + **`MANIFEST.sha256`** (equivalente ao
  installkit maduro) — verificado funcionando do wheel.
- `platformforge upgrade` — reaplica sobre recibo antigo (profile/hosts do
  recibo).
- `platformforge workspace init|add|remove|list|doctor|status` —
  `.platformforge/workspace.json` multi-repo (`platformforge/workspace-manifest/v1`).
- `platformforge mcp integrate|detach` — escreve config de MCP por host
  (ver gaps — fora do ledger).
- `platformforge integrate` — alias do mesmo parity path.

---

## 4. Diagnóstico PyPI (§3.4)

```bash
.venv/bin/python -m build --outdir /tmp/pf-dist .
python3 -m zipfile -l /tmp/pf-dist/platformforge-0.1.6-py3-none-any.whl
tar -tzvf /tmp/pf-dist/platformforge-0.1.6.tar.gz | sort -k3 -rn | head
python3 -m venv /tmp/pf-venv && /tmp/pf-venv/bin/pip install /tmp/pf-dist/*.whl
mkdir /tmp/pf-target && cd /tmp/pf-target && git init .
HOME=/tmp/pf-home /tmp/pf-venv/bin/platformforge install --yes
```

### 4.1 Conteúdo real do wheel (`unzip -l`, resumo)

| Árvore | Arquivos | Origem |
|---|---|---|
| `platformforge/` código | ~303 dirs de 1º nível + módulos | pacote raiz |
| `platformforge/data/contracts` | 24 | force-include `contracts/` |
| `platformforge/data/evals` | 164 | force-include `evals/` |
| `platformforge/data/knowledge` | 14 | force-include `knowledge/` |
| `platformforge/data/lab` | 107 | force-include `lab/` |
| `platformforge/data/portable_skills` | 12 | package data nativa |
| `platformforge/data/rules` | 9 | force-include `rules/` |
| `platformforge/portal_assets` | 46 | force-include `portal/assets/` |
| `forge.json` / `forge.agentic.json` / docs de raiz | **0 — ausentes** | só sdist |

### 4.2 Prova funcional fora do checkout

- `platformforge --version` → 0.1.6; `--help` lista ~60 verbos ✔
- `install --yes` → 51 managed files (201 assets com mirrors) ✔
- `install doctor` → healthy; `mcp-verify` → handshake real PASS (39 tools) ✔
- `lab run-all` → 44/44 passed (do `data/lab` do wheel) ✔
- `evals list`, `knowledge packs` (13), `capability list` (39 caps),
  `agents list` (41) ✔
- `forge manifest` → roda mas **degrada fora de checkout** (ver §5 P1-3)
- `portable build/verify` → bundle + `MANIFEST.sha256` válidos ✔
- `doctor` (runtime) → honesto (`boto3`/`mcp_adapter` = not-installed) ✔
- `install uninstall --purge` → 51 removidos, dirs podados;
  `.platformforge/{materials,receipts}` (runtime) preservados ✔

### 4.3 Comparativo com o publicado (0.1.6)

| Artefato | Local | PyPI | Nota |
|---|---|---|---|
| wheel sha256 | `162be2b8…` | `162be2b8…` | **byte-idêntico — reproduzível** |
| sdist | 83 MB | 3,5 MB | `.tokensave/tokensave.db` (404 MB) no sdist local |

Causa-raiz idêntica à api-forge: `.tokensave/` excluído só em
`.git/info/exclude` (linha 7, local); `.gitignore` não o contém (contém
`.platformforge/` parcialmente com negações para `cases/`/`ledgers/`, que
são rastreados intencionalmente). O sdist local carrega também `.devin`,
`.claude`, `.codex`, `.agents`, `agents/`, `docs/` (251), `tests/` (109),
`evals/`, `lab/`, `contracts/`, `knowledge/`, `portal/`, `scripts/`,
`.platformforge/` (18 entradas — golden/holdout cases rastreados).

---

## 5. Gaps, causa-raiz, riscos, decisões, migração (§3.5)

### P0 — quebra a promessa central do install 2.0

**P0-1 · Nenhuma instrução de entrada chega ao consumidor — sem AGENTS.md,
sem marker, sem protocolo.**
- Evidência: após `install --yes`, `/tmp/pf-target` não tem `AGENTS.md`,
  `CLAUDE.md`, marker ou qualquer doc; `ForgeSpec(marker_files=(),
  marker_body="")` (`install/service.py:62–63`). O host só descobre skills
  e agents por convenção de diretório — nada explica como usá-los, qual o
  contrato, onde estão regras/conhecimento.
- Causa-raiz: o installkit compartilhado suporta markers, mas o spec de
  platform-forge os desativou; não existe AGENT_PROTOCOL.md nesta forja.
- Risco: instalação "muda" — o host vê arquivos mas não sabe operá-los
  (verb-before-answering, PF-* refusal codes, evidence tiers — nada disso
  chega ao contexto).
- Decisão proposta: criar `AGENT_PROTOCOL.md`/marker consumidor mínimo
  (habilitar `marker_files`/`marker_body` no spec) + `.forge/context/`
  com mapa de descoberta.

**P0-2 · MCP não é registrado pelo install; o caminho manual grava comando
quebrado e fora do ledger.**
- Evidência: `install` grava só `.platformforge/mcp.json` (hint).
  `platformforge mcp integrate --host claude` escreveu
  `.mcp.json` com `"command": "python"` — nesta máquina `python` não existe
  (`which python` falhou; só `/usr/bin/python3`). `--host codex` anexa
  `[mcp_servers.platformforge]` a `.codex/config.toml` **a cada chamada**
  (2 blocos após 2 chamadas — TOML inválido por chave duplicada; observado).
- Causa-raiz: `mcp/parity.py` `SERVER_CMD = ["python", "-m", "platformforge",
  "mcp", "serve"]` ignora `platformforge-mcp` (console script) e não dedup;
  escrita fora do ledger → `install status` diz `healthy` enquanto
  `.mcp.json` não é rastreado e `uninstall` não o remove (observado:
  `healthy` com `.mcp.json` não-gerenciado presente).
- Risco: consumidor configura MCP pelo caminho documentado e o servidor
  não sobe (python ausente/errado); drift invisível.
- Decisão proposta: rotear registro MCP pelo managed key do installkit
  (`.mcp.json` com `_forge_managed`), usar `mcp_command` do spec
  (`platformforge-mcp`), dedup/idempotência, e cobrir o caminho `integrate`
  no ledger ou deprecá-lo.

**P0-3 · Registry global `~/.forge/installations/` nunca é escrito pelo
install.**
- Evidência: `install --yes` executado; `/tmp/pf-home/.forge/installations/`
  inexistente. `service.install` não chama `kit.register_installation`
  (contrário a api-forge/data-sentinel).
- Causa-raiz: o adapter `install/service.py` embrulha só o motor nativo;
  o registro ficou delegado ao `forge_bootstrap.py` (fluxo de conta).
- Risco: instalação por wheel/`install` é invisível para descoberta
  cross-forge (`forge collect`, the-forge) — quebra §4.2 do prompt.
- Decisão proposta: registrar `forge/InstallationManifest/v1` no apply e
  deregistrar no uninstall.

### P1 — degradação silenciosa e divergências

**P1-1 · `forge manifest` degrada fora de checkout: `rule_count: 0`.**
- Evidência: `platformforge forge manifest` em `/tmp/pf-target` → warning
  `catalog dir missing: rules/catalog`, `rule_count: 0`, `commit: ""`;
  com `--repo <site-packages>/platformforge/data` → `rule_count: 63`.
- Causa-raiz: `--repo` default `.` (`cli/main.py:227`) e `capability_manifest`
  usa `root/rules/catalog` do cwd em vez de cair para `data_path()` quando
  o cwd não é um checkout.
- Risco: manifesto publicado por uma forja wheel afirma 0 regras — mentira
  por omissão em consumo cross-forge.
- Decisão proposta: fallback `data_path("rules/catalog")` quando o repo não
  tem catálogo; recusar com unlock quando nenhum existe.

**P1-2 · `repair` diverge do contrato do kit: managed modificado nunca é
restaurado.**
- Evidência (código): `install/service.py:284–333` — em conflito, só
  `plan.creates` é restaurado; managed `drift` fica em `kept` ("user content
  by contract"). O kit (`_installkit.repair`) re-escreve managed drifted.
- Impacto: `install repair` não conserta drift de assets — comportamento
  divergente entre forjas com o mesmo nome de verbo. Decisão: documentar a
  divergência como contrato explícito ou alinhar com o kit (re-heal com
  backup — o engine já snapshot-aria via recibo).

**P1-3 · Perfil do contrato é ignorado — sempre `agentic`.**
- Evidência (código): `service.install` valida `minimal|recommended|full`
  mas chama `apply_install(target, "agentic", hosts)`; `--components` é só
  persistido — `minimal` instala os mesmos 201 assets que `full`.
- Risco: perfil documentado mas sem efeito — falso controle de contexto
  (economia). Decisão: mapear perfis para subconjuntos reais ou recusar
  perfis não-implementados honestamente.

**P1-4 · sdist local vaza `.tokensave/` (404 MB).**
- Mesma causa-raiz da api-forge: `.git/info/exclude` local vs `.gitignore`.
  Publicado está limpo (CI), mas build manual de checkout sujo vaza estado.
- Decisão: `.gitignore` commitado + excludes de sdist + gate de conteúdo.

**P1-5 · Quatro cópias de skills sem gerador/gate de drift.**
- `.devin/skills`, `.claude/skills`, `.agents/skills`,
  `platformforge/data/portable_skills` — md5 idênticos hoje; `portal_adapter`
  chama `.devin` de canônico; não há `sync`/`check` para skills (o gate
  `agents check` cobre só mirrors de agents).
- Risco: drift silencioso entre canônico e package data → wheel instala
  skill diferente da editada. Decisão: gerador único + gate (como
  `scripts/sync_skills.py` + `validate_skills.py --check-mirrors` da
  api-forge).

**P1-6 · `forge collect` espera `capability manifest` nas irmãs — verbo
inexistente na api-forge.**
- Evidência: `forge/collect.py` `KNOWN_FORGES["api-forge"] =
  ["capability","manifest"]`; na venv da api-forge: `apiforge capability`
  → `No such command` (existentes: `capabilities list|verify`,
  `forge capabilities`). 
- Risco: ingresso cross-forge quebra no primeiro hop; manifestos ficam
  `unresolved`. Decisão: tabela KNOWN_FORGES por capacidade descoberta
  (probe `forge capabilities`/`capabilities list`) — ou o contrato
  `forge-context/v1` unifica.

### P2 — assimetrias e endurecimento

- **P2-1** — codex recebe `.codex/agents/*.toml` (bom) mas nenhum
  `.codex/config.toml` MCP gerenciado; copilot não recebe `.github/*` —
  decisão documentada ("copilot→agents") vs api-forge (`.github/agents`
  `.agent.md`) — unificar no contrato.
- **P2-2** — `install update` exige registro do bootstrap; sem ele →
  `BLOCKED` (correto, honesto).
- **P2-3** — `.platformforge/{materials,receipts}` sobrevivem a
  `uninstall --purge` (runtime state) — defensável, mas documentar o que
  purge cobre (hoje: `workspace.json` + assets managed; state dir fica).
- **P2-4** — `forge.json`/`forge.agentic.json` fora do wheel — manifesto de
  delegação indisponível p/ consumidor wheel.
- **P2-5** — `mcp serve` imprime banner de help quando chamado sem args
  via `python -m platformforge` (stdout) — inócuo em `mcp serve`, mas
  atenção a stdout limpo no transporte JSON-RPC.
- **P2-6** — `AGENTIC-OS.md` + ~60 docs de raiz não têm equivalente
  consumidor; políticas/steering não são entregues — mesmo problema do P0-1.

### Plano de migração proposto

1. `forge-context/v1`: `.forge/context/{registry,capabilities/<id>.json,
   ROUTING.md}` no apply + registro em `~/.forge/installations/` (P0-2/P0-3).
2. Entrada de instrução no consumidor: habilitar markers
   (`AGENTS.md`+`CLAUDE.md`) ou gerar AGENT_PROTOCOL consumidor (P0-1).
3. MCP: managed key via installkit + `platformforge-mcp` real + dedup +
   cobertura no ledger; deprecar ou consertar `mcp integrate` (P0-2).
4. `forge manifest`/`collect`: fallback `data_path` + tabela de verbos por
   descoberta (P1-1, P1-6).
5. Alinhar `repair`/perfis ao contrato ou documentar divergência (P1-2, P1-3).
6. Skills: gerador único + gate de drift; canônico único (P1-5).
7. sdist excludes + gate de conteúdo (P1-4).

### Compatibilidades observadas

- Wheel byte-idêntico ao publicado → build reproduzível.
- `install` funciona do wheel sem checkout; `lab run-all` passa 44/44.
- MCP stdio próprio sem dep `mcp` → handshake real PASS sem extras.
- Bundle portátil com `MANIFEST.sha256` + verify — padrão installkit
  maduro presente no caminho `portable`.
- Conflito de arquivo do usuário recusa o plano inteiro (fail-closed).
- CI forte: 30+ gates (`scripts/validate.py --gate …`), job `package` que
  constrói wheel, instala em venv limpa e faz smoke **fora do checkout**
  (`ci.yml:119–145`), `publish-pypi.yml` com version gate + trusted
  publishing + verify pós-publicação.
- Testes: `tests/test_install_lifecycle.py`, `test_portable_distribution.py`,
  `test_portable_workspace.py`, `test_artifact_contents.py`,
  `test_agent_mirrors.py` (drift gate de mirrors).

## Apêndice — comandos executados

```text
git log -1 --format='%H %s'                                    # b58dc9c…
md5sum platformforge/_installkit.py                            # a31bd4f0… == siblings
cmp -s scripts/forge_installkit.py platformforge/_installkit.py # IDÊNTICO
.venv/bin/python -m build --outdir /tmp/pf-dist .
python3 -m zipfile -l /tmp/pf-dist/platformforge-0.1.6-py3-none-any.whl
tar -tzvf /tmp/pf-dist/platformforge-0.1.6.tar.gz | sort -k3 -rn | head
sha256sum /tmp/pf-dist/*.whl                                   # == PyPI
python3 -m venv /tmp/pf-venv; /tmp/pf-venv/bin/pip install …whl
cd /tmp/pf-target && git init
HOME=/tmp/pf-home /tmp/pf-venv/bin/platformforge install --yes
platformforge install status|doctor|repair|uninstall|update|mcp-verify
platformforge knowledge packs|evals list|capability list|agents list|lab run-all
platformforge forge manifest [--repo …] | doctor | hosts | ai | mcp integrate
platformforge portable build /tmp/pf-bundle … | portable verify /tmp/pf-bundle
platformforge install --scope user --yes                       # HOME=/tmp/pf-home2
```
