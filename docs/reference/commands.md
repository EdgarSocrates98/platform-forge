# `platformforge` command reference

Generated from the real CLI parser by `doc_inventory.py` + `doc_reference.py`. Do not hand-edit generated sections — write between `keep:start`/`keep:end` markers. `por que`/`quando` lines come from the curated `command-rationale.json` — edit rationale there, never here. Status vocabulary: `available` unless marked otherwise.

Rationale coverage: **57/57** first-level groups curated in `command-rationale.json`.

## Groups

- [`agents`](#agents) — 1 command(s)
- [`ai`](#ai) — 1 command(s)
- [`analytics`](#analytics) — 1 command(s)
- [`analyze`](#analyze) — 1 command(s)
- [`bench`](#bench) — 1 command(s)
- [`cache`](#cache) — 1 command(s)
- [`capability`](#capability) — 1 command(s)
- [`cases`](#cases) — 1 command(s)
- [`caveman`](#caveman) — 1 command(s)
- [`change`](#change) — 1 command(s)
- [`collect`](#collect) — 1 command(s)
- [`context`](#context) — 1 command(s)
- [`correlate`](#correlate) — 1 command(s)
- [`diagnose`](#diagnose) — 1 command(s)
- [`diff`](#diff) — 1 command(s)
- [`doctor`](#doctor) — 1 command(s)
- [`drift`](#drift) — 1 command(s)
- [`economy`](#economy) — 1 command(s)
- [`evals`](#evals) — 1 command(s)
- [`explain`](#explain) — 1 command(s)
- [`federation`](#federation) — 1 command(s)
- [`finops`](#finops) — 1 command(s)
- [`fleet`](#fleet) — 1 command(s)
- [`forge`](#forge) — 1 command(s)
- [`freeze`](#freeze) — 1 command(s)
- [`graph`](#graph) — 1 command(s)
- [`impact`](#impact) — 1 command(s)
- [`init`](#init) — 1 command(s)
- [`inspect`](#inspect) — 1 command(s)
- [`install`](#install) — 1 command(s)
- [`integrate`](#integrate) — 1 command(s)
- [`judge`](#judge) — 1 command(s)
- [`knowledge`](#knowledge) — 1 command(s)
- [`lab`](#lab) — 1 command(s)
- [`live`](#live) — 1 command(s)
- [`mcp`](#mcp) — 1 command(s)
- [`observe`](#observe) — 1 command(s)
- [`ops`](#ops) — 1 command(s)
- [`optimize`](#optimize) — 1 command(s)
- [`plan`](#plan) — 1 command(s)
- [`policy`](#policy) — 1 command(s)
- [`portable`](#portable) — 1 command(s)
- [`product`](#product) — 1 command(s)
- [`recommend`](#recommend) — 1 command(s)
- [`reliability`](#reliability) — 1 command(s)
- [`risk`](#risk) — 1 command(s)
- [`route`](#route) — 1 command(s)
- [`routing`](#routing) — 1 command(s)
- [`rtk`](#rtk) — 1 command(s)
- [`sdd`](#sdd) — 1 command(s)
- [`security`](#security) — 1 command(s)
- [`status`](#status) — 1 command(s)
- [`store`](#store) — 1 command(s)
- [`tokens`](#tokens) — 1 command(s)
- [`uninstall`](#uninstall) — 1 command(s)
- [`upgrade`](#upgrade) — 1 command(s)
- [`workspace`](#workspace) — 1 command(s)

## agents

### `agents`

**para que:** agent roster, mirrors, referee

- **por que:** roster de agentes, mirrors e referee
- **quando usar:** inspecionar quem pode executar antes de delegar

**Syntax**

```text
platformforge agents [help] [json] [FILE] [detail_level] [offline] [strict] [repo] <agents_cmd> [path] [name] [domain]
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `agents_cmd` | yes | — | — |
| `path` | no | — | — |
| `name` | no | — | — |
| `domain` | no | — | — |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## ai

### `ai`

**para que:** AI platform awareness (bounded)

- **por que:** consciência de plataforma de IA (bounded)
- **quando usar:** perguntas sobre capabilities de IA declaradas

**Syntax**

```text
platformforge ai [help] [json] [FILE] [detail_level] [offline] [strict] [repo] <ai_cmd> [path] [cost] [denominators]
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `ai_cmd` | yes | — | — |
| `path` | no | — | yaml input (resources / capacity doc) |
| `cost` | no | — | — |
| `denominators` | no | — | JSON {tokens,inferences,gpu_hours} |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## analytics

### `analytics`

**para que:** analytics summary/metric/maturity

- **por que:** summary/metric/maturity analíticos
- **quando usar:** visão agregada de métricas e maturidade

**Syntax**

```text
platformforge analytics [help] [json] [FILE] [detail_level] [offline] [strict] [repo] <analytics_cmd> [path] [id]
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `analytics_cmd` | yes | — | — |
| `path` | no | — | — |
| `id` | no | — | metric id |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## analyze

### `analyze`

**para que:** domain analyzers → facts

- **por que:** extrai facts determinísticos por domínio (secrets/iam/sbom/supply/drift...)
- **quando usar:** inventário factual antes de judge/explain

**Syntax**

```text
platformforge analyze [help] [json] [FILE] [detail_level] [offline] [strict] [repo] <analyze_cmd> [facts] [path] [config] [state] [vulns] [kyverno_version]
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `analyze_cmd` | yes | — | — |
| `facts` | no | — | facts doc for ownership/contradiction joins |
| `path` | no | — | — |
| `config` | no | — | — |
| `state` | no | — | — |
| `vulns` | no | — | offline vuln list JSON |
| `kyverno_version` | no | — | declared kyverno version for deprecation checks |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## bench

### `bench`

**para que:** §148–150 measured benchmarks

- **por que:** benchmark medido entre runs
- **quando usar:** comparar performance com dados observados

**Syntax**

```text
platformforge bench [help] [json] [FILE] [detail_level] [offline] [strict] [repo] [bench_cmd] [repeat] [sizes] [edges] [events]
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `bench_cmd` | no | — | — |
| `repeat` | no | — | — |
| `sizes` | no | — | comma list for scale bench (default 50,200,800) |
| `edges` | no | — | comma list for edge sweep (default 100000,250000,500000) |
| `events` | no | — | also run the analytics store event sweep (10k/100k/1M) |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## cache

### `cache`

**para que:** multilayer cache stats/inspect/invalidate/gc

- **por que:** cache de evidência incremental — reusa só o que é fresco
- **quando usar:** inspecionar/limpar o que está cacheado

**Syntax**

```text
platformforge cache [help] [json] [FILE] [detail_level] [offline] [strict] [repo] <cache_cmd> [layer] [key] [scope] [deps] [dep] [value]
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `cache_cmd` | yes | — | — |
| `layer` | no | — | — |
| `key` | no | — | — |
| `scope` | no | — | — |
| `deps` | no | — | — |
| `dep` | no | — | — |
| `value` | no | — | — |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## capability

### `capability`

**para que:** capability registry

- **por que:** superfície de capabilities: list/describe/check
- **quando usar:** perguntar o que a forja declara atender

**Syntax**

```text
platformforge capability [help] [json] [FILE] [detail_level] [offline] [strict] [repo] <capability_cmd> [name] [domain] [version]
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `capability_cmd` | yes | — | — |
| `name` | no | — | — |
| `domain` | no | — | §139 — domain to negotiate, e.g. k8s |
| `version` | no | — | §139 — product version to check support for |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## cases

### `cases`

**para que:** real-world case corpus + replay

- **por que:** gerencia cases que ancoram findings e evidência
- **quando usar:** iniciar/inspecionar o caso sob análise

**Syntax**

```text
platformforge cases [help] [json] [FILE] [detail_level] [offline] [strict] [repo] <cases_cmd> [path] [tier] [out] [stamp]
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `cases_cmd` | yes | — | — |
| `path` | no | — | — |
| `tier` | no | — | — |
| `out` | no | — | challenger routing.yaml for route-bench |
| `stamp` | no | — | context-audit: write measured context_cost back into case.yaml |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## caveman

### `caveman`

**para que:** compress text (caveman)

- **por que:** workflows caveman — protocolo de coordenação host-neutral
- **quando usar:** executar decomposição de coordenador em passos

**Syntax**

```text
platformforge caveman [help] [json] [FILE] [detail_level] [offline] [strict] [repo] <file> [mode] [context_risk]
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `file` | yes | — | file to compress ('-' = stdin) |
| `mode` | no | — | — |
| `context_risk` | no | — | — |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## change

### `change`

**para que:** §85–86 change lifecycle (sandboxed)

- **por que:** review de mudança proposta; approve/apply ficam host-side
- **quando usar:** revisar uma mudança — mutação só via gate de política

**Syntax**

```text
platformforge change [help] [json] [FILE] [detail_level] [offline] [strict] [repo] <change_cmd> [patch] [file] [signals]
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `change_cmd` | yes | — | — |
| `patch` | no | — | unified diff file |
| `file` | no | — | rel/path=src-file (or literal content) |
| `signals` | no | — | JSON risk signals doc (review only) |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## collect

### `collect`

**para que:** ingest artifact dumps → facts

- **por que:** coleta de evidência em dumps offline
- **quando usar:** trazer artefatos do ambiente para análise local

**Syntax**

```text
platformforge collect [help] [json] [FILE] [detail_level] [offline] [strict] [repo] [path]
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `path` | no | — | — |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## context

### `context`

**para que:** context pack for a task; capsule/inspect/expand/delta/gc

- **por que:** resolução de contexto por workspace
- **quando usar:** montar o contexto certo sob escopo declarado

**Syntax**

```text
platformforge context [help] [json] [FILE] [detail_level] [offline] [strict] [repo] [context_cmd] [task] [input_budget] [changed] [scope] [budget_bytes] [essential_bytes] [required] [role] [facts] [findings] [rules] [knowledge] [graph_refs] [questions] [ref] [section]
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `context_cmd` | no | — | — |
| `task` | no | — | — |
| `input_budget` | no | — | — |
| `changed` | no | — | — |
| `scope` | no | — | — |
| `budget_bytes` | no | — | — |
| `essential_bytes` | no | — | — |
| `required` | no | — | — |
| `role` | no | — | — |
| `facts` | no | — | — |
| `findings` | no | — | — |
| `rules` | no | — | — |
| `knowledge` | no | — | — |
| `graph_refs` | no | — | — |
| `questions` | no | — | — |
| `ref` | no | — | — |
| `section` | no | — | — |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## correlate

### `correlate`

**para que:** OTel correlation (observe otel)

- **por que:** correlação de sinais de incidente/telemetria
- **quando usar:** ligar sintomas a causas com dependência declarada

**Syntax**

```text
platformforge correlate [help] [json] [FILE] [detail_level] [offline] [strict] [repo] <path>
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `path` | yes | — | — |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## diagnose

### `diagnose`

**para que:** node diagnosis: facts+findings+blast

- **por que:** diagnóstico offline sobre bundle de evidência
- **quando usar:** falha sem causa clara — correlaciona evidência já coletada

**Syntax**

```text
platformforge diagnose [help] [json] [FILE] [detail_level] [offline] [strict] [repo] <node> [findings] [facts]
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `node` | yes | — | — |
| `findings` | no | — | — |
| `facts` | no | — | — |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## diff

### `diff`

**para que:** graph diff between two facts docs

- **por que:** o que mudou entre dois estados/snapshots
- **quando usar:** comparar estado antes/depois de uma mudança

**Syntax**

```text
platformforge diff [help] [json] [FILE] [detail_level] [offline] [strict] [repo] <before> <after>
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `before` | yes | — | — |
| `after` | yes | — | — |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## doctor

### `doctor`

**para que:** environment health-check

- **por que:** self-check de ambiente, instalação e capabilities
- **quando usar:** primeira linha de troubleshooting local — nunca toca rede

**Syntax**

```text
platformforge doctor [help] [json] [FILE] [detail_level] [offline] [strict] [repo] [deep]
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `deep` | no | — | §141 contract checks (config, manifest, knowledge, parity, index, store) |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## drift

### `drift`

**para que:** IaC drift: --config dir vs --state file

- **por que:** detecta drift entre estado declarado e observado
- **quando usar:** verificar se o ambiente divergiu da declaração

**Syntax**

```text
platformforge drift [help] [json] [FILE] [detail_level] [offline] [strict] [repo] <config> <state>
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `config` | yes | — | — |
| `state` | yes | — | — |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## economy

### `economy`

**para que:** economy engine report/strategy/qpt

- **por que:** economia medida da execução
- **quando usar:** entender o custo real de contexto/descoberta

**Syntax**

```text
platformforge economy [help] [json] [FILE] [detail_level] [offline] [strict] [repo] [economy_cmd] [signal] [path] [task] [input_budget] [versions] [run_id] [spent] [remaining] [deps] [profile] [planned] [observed]
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `economy_cmd` | no | — | — |
| `signal` | no | — | JSON TaskSignal (strategy/compare) |
| `path` | no | — | facts doc for qpt |
| `task` | no | — | — |
| `input_budget` | no | — | — |
| `versions` | no | — | JSON product versions for qpt, e.g. '{"kubernetes": "1.29"}' |
| `run_id` | no | — | — |
| `spent` | no | — | JSON spent budget (checkpoint) |
| `remaining` | no | — | JSON remaining budget |
| `deps` | no | — | JSON dep hashes (checkpoint) |
| `profile` | no | — | routing profile (resume) |
| `planned` | no | — | JSON planned usage (reconcile) |
| `observed` | no | — | JSON observed usage (reconcile) |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## evals

### `evals`

**para que:** eval framework (§94–95)

- **por que:** matriz de avaliação declarativa, goldens e holdout
- **quando usar:** validar qualidade determinística antes de release

**Syntax**

```text
platformforge evals [help] [json] [FILE] [detail_level] [offline] [strict] [repo] [evals_cmd] [type] [cases]
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `evals_cmd` | no | — | — |
| `type` | no | — | — |
| `cases` | no | — | — |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## explain

### `explain`

**para que:** evidence chain for a finding

- **por que:** explica um finding: regra, evidência, raciocínio
- **quando usar:** entender por que um rule_id disparou

**Syntax**

```text
platformforge explain [help] [json] [FILE] [detail_level] [offline] [strict] [repo] <path> [name] [facts]
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `path` | yes | — | findings doc (json) |
| `name` | no | — | finding_id or rule_id |
| `facts` | no | — | facts doc (json) |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## federation

### `federation`

**para que:** intelligence exchange — no credentials

- **por que:** federação de forjas/workspaces
- **quando usar:** coordenar escopo multi-forja declarado

**Syntax**

```text
platformforge federation [help] [json] [FILE] [detail_level] [offline] [strict] [repo] <federation_cmd> [path] [question] [nodes] [classification] [manifest] [node_id] [capabilities] [freshness] [limit]
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `federation_cmd` | yes | — | — |
| `path` | no | — | payload yaml (export) |
| `question` | no | — | fleet question (query) |
| `nodes` | no | — | fleet dirs (query) |
| `classification` | no | — | — |
| `manifest` | no | — | — |
| `node_id` | no | — | — |
| `capabilities` | no | — | — |
| `freshness` | no | — | — |
| `limit` | no | — | — |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## finops

### `finops`

**para que:** FinOps cost analysis

- **por que:** custo: costs/ingest/unit/report sobre dados medidos
- **quando usar:** decidir por custo com baseline real, nunca estimativa

**Syntax**

```text
platformforge finops [help] [json] [FILE] [detail_level] [offline] [strict] [repo] <finops_cmd> [path] [by] [denominators]
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `finops_cmd` | yes | — | — |
| `path` | no | — | — |
| `by` | no | — | — |
| `denominators` | no | — | JSON {unit: measured_count} for `finops unit` |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## fleet

### `fleet`

**para que:** fleet intelligence (dir input)

- **por que:** inteligência de frota/estate sobre manifesto multi-repo
- **quando usar:** perguntas agregadas sobre muitos repos

**Syntax**

```text
platformforge fleet [help] [json] [FILE] [detail_level] [offline] [strict] [repo] <fleet_cmd> [path] [question] [limit] [window]
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `fleet_cmd` | yes | — | — |
| `path` | no | — | fleet dir (lab/fleets/acme shape) |
| `question` | no | — | risks: run a single fleet question |
| `limit` | no | — | — |
| `window` | no | — | drift window (24h/7d/30d/90d) |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## forge

### `forge`

**para que:** Forge interop

- **por que:** Forge Protocol: capabilities, task, handoff, health
- **quando usar:** interoperar com o control plane The Forge

**Syntax**

```text
platformforge forge [help] [json] [FILE] [detail_level] [offline] [strict] [repo] <forge_cmd> [path] [name] [src] [dst]
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `forge_cmd` | yes | — | — |
| `path` | no | — | — |
| `name` | no | — | — |
| `src` | no | — | — |
| `dst` | no | — | — |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## freeze

### `freeze`

**para que:** architecture freeze governance

- **por que:** congela estado/snapshot para comparação
- **quando usar:** fixar baseline antes de avaliar drift

**Syntax**

```text
platformforge freeze [help] [json] [FILE] [detail_level] [offline] [strict] [repo] <freeze_cmd> [path] [out] [json_file]
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `freeze_cmd` | yes | — | — |
| `path` | no | — | — |
| `out` | no | — | — |
| `json_file` | no | — | FeatureException JSON for `freeze exception` |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## graph

### `graph`

**para que:** Graphfy platform graph

- **por que:** grafo da plataforma: deps/blast/paths e identidade
- **quando usar:** perguntas de dependência, impacto ou identidade

**Syntax**

```text
platformforge graph [help] [json] [FILE] [detail_level] [offline] [strict] [repo] <graph_cmd> [facts] [node] [src] [dst] [before] [after] [at] [edge_id] [source_type] [no_browser] [port] [snapshot]
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `graph_cmd` | yes | — | — |
| `facts` | no | — | — |
| `node` | no | — | — |
| `src` | no | — | — |
| `dst` | no | — | — |
| `before` | no | — | — |
| `after` | no | — | — |
| `at` | no | — | at: ISO timestamp |
| `edge_id` | no | — | timeline: edge id |
| `source_type` | no | — | §6 snapshot type for `graph build` |
| `no_browser` | no | — | graph ui: serve without opening a browser (SSH/remote) |
| `port` | no | — | graph ui: port (default ephemeral) |
| `snapshot` | no | — | graph view: emit the view of a saved snapshot hash |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## impact

### `impact`

**para que:** blast radius for a graph node

- **por que:** impacto de uma mudança sobre o grafo de dependências
- **quando usar:** antes de aplicar: quem quebra se eu mudar isto

**Syntax**

```text
platformforge impact [help] [json] [FILE] [detail_level] [offline] [strict] [repo] <node>
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `node` | yes | — | — |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## init

### `init`

**para que:** scaffold .platformforge/

- **por que:** inicializa o estado mínimo local da forja
- **quando usar:** primeiro passo num diretório ainda não configurado

**Syntax**

```text
platformforge init [help] [json] [FILE] [detail_level] [offline] [strict] [repo] [name]
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `name` | no | — | — |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## inspect

### `inspect`

**para que:** inventory analyzable artifacts

- **por que:** inspeção de artefatos do repo e postura declarada
- **quando usar:** perguntar sobre artefatos — rode o verbo antes de ler o arquivo

**Syntax**

```text
platformforge inspect [help] [json] [FILE] [detail_level] [offline] [strict] [repo]
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## install

### `install`

**para que:** install Platform Forge assets into a workspace

- **por que:** instala Platform Forge num projeto, workspace ou home do usuário
- **quando usar:** ativar a forja num escopo governado pela primeira vez

**Syntax**

```text
platformforge install [help] [json] [FILE] [detail_level] [offline] [strict] [repo] [op] [profile] [host] [scope] [yes] [purge] [to] [components] [dry_run]
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `op` | no | — | forge/* lifecycle verb (default: apply) |
| `profile` | no | — | minimal|recommended|full (contract) or native profile name |
| `host` | no | — | — |
| `scope` | no | — | — |
| `yes` | no | — | explicit approval — required for writes |
| `purge` | no | — | uninstall: also remove .platformforge state |
| `to` | no | — | update: pinned version — never 'latest' |
| `components` | no | — | optional components csv: skills,agents,mcp,tui,graph-studio |
| `dry_run` | no | — | — |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## integrate

### `integrate`

**para que:** host integration (mcp parity)

- **por que:** instala skills/agents/MCP nos hosts do usuário
- **quando usar:** ativar a forja no Claude/Codex/Devin

**Syntax**

```text
platformforge integrate [help] [json] [FILE] [detail_level] [offline] [strict] [repo] <host> [detach]
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `host` | yes | — | — |
| `detach` | no | — | — |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## judge

### `judge`

**para que:** apply rule catalog to facts

- **por que:** aplica o catálogo de regras sobre facts extraídos
- **quando usar:** depois do analyze/collect: facts viram findings com rule_id

**Syntax**

```text
platformforge judge [help] [json] [FILE] [detail_level] [offline] [strict] [repo] <facts> [catalog] [versions]
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `facts` | yes | — | — |
| `catalog` | no | — | — |
| `versions` | no | — | JSON product versions, e.g. '{"kubernetes": "1.29"}' |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## knowledge

### `knowledge`

**para que:** knowledge freshness/drift check

- **por que:** knowledge packs versionados e proveniência
- **quando usar:** consultar a fonte canônica de regras e matrizes

**Syntax**

```text
platformforge knowledge [help] [json] [FILE] [detail_level] [offline] [strict] [repo] [knowledge_cmd]
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `knowledge_cmd` | no | — | — |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## lab

### `lab`

**para que:** Forge Lab scenarios

- **por que:** Forge Lab: cenários reproduzíveis offline
- **quando usar:** experimentar sem tocar o ambiente real

**Syntax**

```text
platformforge lab [help] [json] [FILE] [detail_level] [offline] [strict] [repo] <lab_cmd> [path] [allow_prod] [profile] [allow_profile]
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `lab_cmd` | yes | — | — |
| `path` | no | — | — |
| `allow_prod` | no | — | chaos: allow env:production targets |
| `profile` | no | — | §118 lab profile filter |
| `allow_profile` | no | — | §119 — opt into non-static lab profiles |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## live

### `live`

**para que:** live platform observation (cycle3)

- **por que:** superfície live/opt-in de observação
- **quando usar:** observação de runtime quando o modo live está habilitado

**Syntax**

```text
platformforge live [help] [json] [FILE] [detail_level] [offline] [strict] [repo] <live_cmd> [provider] [region] [service] [deep] [context] [namespace] [resource_type] [selector] [namespaced_only] [no_store] [desired] [planned] [observed] [no_observed] [otel] [hubble] [slices] [apply_to_graph] [register] [before] [after] [incident] [changes] [events_file] [collect] [gc] [since] [until] [resource] [events] [window] [drift_events] [max_objects] [max_api_calls] [max_bytes]
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `live_cmd` | yes | — | — |
| `provider` | no | — | — |
| `region` | no | — | aws: restrict regions (repeatable) |
| `service` | no | — | aws: restrict services (repeatable) |
| `deep` | no | — | doctor: probe every provider adapter |
| `context` | no | — | kube context |
| `namespace` | no | — | restrict to namespace (repeatable) |
| `resource_type` | no | — | restrict resource types (repeatable) |
| `selector` | no | — | k8s label selector |
| `namespaced_only` | no | — | rbac: emit Role instead of ClusterRole |
| `no_store` | no | — | snapshot: emit envelope without persisting |
| `desired` | no | — | reconcile: facts.json path (default: repo scan) |
| `planned` | no | — | reconcile: planned facts.json path |
| `observed` | no | — | reconcile: observation_id or envelope.json |
| `no_observed` | no | — | reconcile: desired↔planned only |
| `otel` | no | — | topology: OTLP spans json |
| `hubble` | no | — | topology: hubble flows |
| `slices` | no | — | topology: endpointslices json |
| `apply_to_graph` | no | — | topology: persist runtime edges into graph |
| `register` | no | — | clusters: register cluster JSON spec |
| `before` | no | — | drift: obs id/file |
| `after` | no | — | drift: obs id/file |
| `incident` | no | — | incident: incident JSON {timestamp,resources} |
| `changes` | no | — | incident: candidate changes JSON list |
| `events_file` | no | — | changes: append ChangeEvents from JSON file (offline-safe) |
| `collect` | no | — | changes: collect via provider adapter (host-side) |
| `gc` | no | — | changes: garbage-collect the change journal |
| `since` | no | — | changes: events after ISO ts |
| `until` | no | — | changes: events before ISO ts |
| `resource` | no | — | changes: filter by resource id |
| `events` | no | — | incident: timeline events JSON list |
| `window` | no | — | incident: correlation window seconds |
| `drift_events` | no | — | plan: drift events JSON (default: diff latest two stored observations) |
| `max_objects` | no | — | — |
| `max_api_calls` | no | — | — |
| `max_bytes` | no | — | — |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## mcp

### `mcp`

**para que:** MCP server + host parity

- **por que:** servidor MCP e inspeção de catálogo
- **quando usar:** servir a forja via MCP ou conferir a superfície exposta

**Syntax**

```text
platformforge mcp [help] [json] [FILE] [detail_level] [offline] [strict] [repo] <mcp_cmd> [path] [name] [input] [host]
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `mcp_cmd` | yes | — | — |
| `path` | no | — | — |
| `name` | no | — | — |
| `input` | no | — | — |
| `host` | no | — | — |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## observe

### `observe`

**para que:** SRE/observability verbs

- **por que:** observabilidade: slo/incident/otel sobre evidência
- **quando usar:** perguntas de SLO, incidente ou telemetria

**Syntax**

```text
platformforge observe [help] [json] [FILE] [detail_level] [offline] [strict] [repo] <observe_cmd> [path] [sli] [windows] [alerts] [changes] [incident] [facts] [window]
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `observe_cmd` | yes | — | — |
| `path` | no | — | — |
| `sli` | no | — | JSON {good,bad,total}_events |
| `windows` | no | — | JSON {window: {good,bad}} for slo-burn |
| `alerts` | no | — | — |
| `changes` | no | — | — |
| `incident` | no | — | incident JSON for postmortem |
| `facts` | no | — | facts JSON for dr |
| `window` | no | — | — |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## ops

### `ops`

**para que:** governed operations (cycle4)

- **por que:** operações de plataforma
- **quando usar:** tarefas operacionais declaradas no escopo da forja

**Syntax**

```text
platformforge ops [help] [json] [FILE] [detail_level] [offline] [strict] [repo] <ops_cmd> [intent] [plan] [spec] [policies] [environment] [level] [execute] [request] [name] [bind] [name_pos] [operation_id] [post_rollback] [resource] [evidence_tier] [approval_id] [subject_hash] [subject_kind] [actor] [actor_kind] [role] [approval_type] [expires_at] [bounds] [scope] [reason]
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `ops_cmd` | yes | — | — |
| `intent` | no | — | intent JSON file |
| `plan` | no | — | plan JSON/YAML file |
| `spec` | no | — | ops run spec YAML/JSON |
| `policies` | no | — | policies YAML list |
| `environment` | no | — | — |
| `level` | no | — | — |
| `execute` | no | — | real mutation — requires hash-bound approval + host transports; default is dry-run |
| `request` | no | — | delegate request JSON |
| `name` | no | — | runbook id (positional name overrides) |
| `bind` | no | — | runbook bind params JSON |
| `name_pos` | no | — | runbook id or 'list' |
| `operation_id` | no | — | — |
| `post_rollback` | no | — | rollback: post-rollback observation JSON {step_id: {dim: value}} for verification |
| `resource` | no | — | history filter |
| `evidence_tier` | no | — | autorem-eval |
| `approval_id` | no | — | — |
| `subject_hash` | no | — | envelope/plan hash being approved |
| `subject_kind` | no | — | — |
| `actor` | no | — | human identity |
| `actor_kind` | no | — | — |
| `role` | no | — | — |
| `approval_type` | no | — | — |
| `expires_at` | no | — | — |
| `bounds` | no | — | parameter bounds JSON |
| `scope` | no | — | csv resource scope |
| `reason` | no | — | — |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## optimize

### `optimize`

**para que:** optimization scan → ChangeIntent only

- **por que:** candidatos de otimização com evidência
- **quando usar:** depois do analyze: priorizar o que otimizar

**Syntax**

```text
platformforge optimize [help] [json] [FILE] [detail_level] [offline] [strict] [repo] <optimize_cmd> [path] [id] [out] [limit]
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `optimize_cmd` | yes | — | — |
| `path` | no | — | — |
| `id` | no | — | recommendation id |
| `out` | no | — | plan: write the ChangeIntent doc to this file |
| `limit` | no | — | — |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## plan

### `plan`

**para que:** findings → ordered remediation plan

- **por que:** planejamento composto sobre facts já extraídos
- **quando usar:** revisar passos antes de executar trabalho multi-passo

**Syntax**

```text
platformforge plan [help] [json] [FILE] [detail_level] [offline] [strict] [repo] <path> [facts]
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `path` | yes | — | — |
| `facts` | no | — | — |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## policy

### `policy`

**para que:** policy-as-code catalog check

- **por que:** avalia ações contra o catálogo de políticas
- **quando usar:** checar permissão/veredito antes de uma ação

**Syntax**

```text
platformforge policy [help] [json] [FILE] [detail_level] [offline] [strict] [repo] <policy_cmd> [path]
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `policy_cmd` | yes | — | — |
| `path` | no | — | — |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## portable

### `portable`

**para que:** build/verify/doctor portable distributions

- **por que:** distribuição portátil offline
- **quando usar:** operar a forja em ambiente sem rede

**Syntax**

```text
platformforge portable [help] [json] [FILE] [detail_level] [offline] [strict] [repo] <portable_cmd> [path] [profile] [host] [offline_bundle]
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `portable_cmd` | yes | — | — |
| `path` | no | — | — |
| `profile` | no | — | — |
| `host` | no | — | — |
| `offline_bundle` | no | — | — |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## product

### `product`

**para que:** platform product verbs

- **por que:** superfície de produto declarada
- **quando usar:** consultar capabilities de produto da plataforma

**Syntax**

```text
platformforge product [help] [json] [FILE] [detail_level] [offline] [strict] [repo] <product_cmd> [signals] [findings] [facts] [id]
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `product_cmd` | yes | — | — |
| `signals` | no | — | JSON signals doc |
| `findings` | no | — | findings JSON doc |
| `facts` | no | — | facts JSON for analysis |
| `id` | no | — | golden path id |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## recommend

### `recommend`

**para que:** findings → recommendations

- **por que:** recomendações derivadas de findings
- **quando usar:** priorizar ações a partir dos findings julgados

**Syntax**

```text
platformforge recommend [help] [json] [FILE] [detail_level] [offline] [strict] [repo] <path>
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `path` | yes | — | findings doc (json) |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## reliability

### `reliability`

**para que:** SRE+K8S rules over facts

- **por que:** SLO e caminho crítico de confiabilidade
- **quando usar:** avaliar resiliência end-to-end com evidência

**Syntax**

```text
platformforge reliability [help] [json] [FILE] [detail_level] [offline] [strict] [repo] [path]
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `path` | no | — | — |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## risk

### `risk`

**para que:** §130 change-risk assessment

- **por que:** avaliação de risco de mudança proposta
- **quando usar:** classificar risco antes de aplicar

**Syntax**

```text
platformforge risk [help] [json] [FILE] [detail_level] [offline] [strict] [repo] [node] [signals]
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `node` | no | — | graph node id to assess |
| `signals` | no | — | JSON signals doc |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## route

### `route`

**para que:** adaptive routing decision

- **por que:** roteamento determinístico para o especialista certo
- **quando usar:** decidir qual agente/domínio atende a pergunta

**Syntax**

```text
platformforge route [help] [json] [FILE] [detail_level] [offline] [strict] [repo] <signal>
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `signal` | yes | — | JSON TaskSignal |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## routing

### `routing`

**para que:** routing explain/compare/scorecard

- **por que:** tabela de roteamento declarada
- **quando usar:** inspecionar como requests são roteados

**Syntax**

```text
platformforge routing [help] [json] [FILE] [detail_level] [offline] [strict] [repo] <routing_cmd> [task] [profile] [risk] [signal] [estimated] [champion] [challenger] [approved] [run_id] [mode] [correctness] [tokens] [agents] [provider_calls]
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `routing_cmd` | yes | — | — |
| `task` | no | — | — |
| `profile` | no | — | — |
| `risk` | no | — | — |
| `signal` | no | — | — |
| `estimated` | no | — | — |
| `champion` | no | — | — |
| `challenger` | no | — | — |
| `approved` | no | — | — |
| `run_id` | no | — | — |
| `mode` | no | — | — |
| `correctness` | no | — | — |
| `tokens` | no | — | — |
| `agents` | no | — | — |
| `provider_calls` | no | — | — |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## rtk

### `rtk`

**para que:** compact command output (rtk)

- **por que:** protocolo RTK de redução de contexto
- **quando usar:** compactar saída antes de alimentar um host/agente

**Syntax**

```text
platformforge rtk [help] [json] [FILE] [detail_level] [offline] [strict] [repo] [rtk_cmd] [file] [command] [exit_code] [artifact] [start] [end] [pattern]
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `rtk_cmd` | no | — | — |
| `file` | no | — | output file to compact ('-' = stdin) |
| `command` | no | — | command that produced output |
| `exit_code` | no | — | — |
| `artifact` | no | — | — |
| `start` | no | — | — |
| `end` | no | — | — |
| `pattern` | no | — | — |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## sdd

### `sdd`

**para que:** native SDD lifecycle

- **por que:** spec-driven development: cadeia de artefatos e gates
- **quando usar:** trabalho não-trivial: discover→define→contract→design→plan→build→verify→review→ship

**Syntax**

```text
platformforge sdd [help] [json] [FILE] [detail_level] [offline] [strict] [repo] <sdd_cmd> <feature> [body] [phase] [verify] [risk_accepted] [override] [override_reason]
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `sdd_cmd` | yes | — | — |
| `feature` | yes | — | — |
| `body` | no | — | artifact body or JSON |
| `phase` | no | — | stamp single phase |
| `verify` | no | — | verify JSON for ship gate |
| `risk_accepted` | no | — | — |
| `override` | no | — | — |
| `override_reason` | no | — | — |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## security

### `security`

**para que:** security bundle (secrets+iam+sbom+supply)

- **por que:** superfície de segurança: secrets, iam, supply
- **quando usar:** perguntas de postura e exposição

**Syntax**

```text
platformforge security [help] [json] [FILE] [detail_level] [offline] [strict] [repo] [path]
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `path` | no | — | — |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## status

### `status`

**para que:** workspace + store status

- **por que:** resumo do estado do projeto/workspace
- **quando usar:** visão rápida antes de qualquer verbo de análise

**Syntax**

```text
platformforge status [help] [json] [FILE] [detail_level] [offline] [strict] [repo]
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## store

### `store`

**para que:** §151 artifact store stats/gc

- **por que:** store local de fatos/snapshots
- **quando usar:** persistir e recuperar evidência entre sessões

**Syntax**

```text
platformforge store [help] [json] [FILE] [detail_level] [offline] [strict] [repo] <store_cmd> [keep_days] [execute]
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `store_cmd` | yes | — | — |
| `keep_days` | no | — | — |
| `execute` | no | — | actually delete (default: dry-run) |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## tokens

### `tokens`

**para que:** tokensave: index/search/pack/delta/stats/ledger

- **por que:** contabilidade de contexto em bytes, não tokens estimados
- **quando usar:** medir custo de contexto de forma honesta

**Syntax**

```text
platformforge tokens [help] [json] [FILE] [detail_level] [offline] [strict] [repo] <tokens_cmd> [task] [query] [mode] [limit] [changed] [input_budget] [risk] [graph_nodes] [prev_pack] [allow_escalate]
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `tokens_cmd` | yes | — | — |
| `task` | no | — | — |
| `query` | no | — | — |
| `mode` | no | — | — |
| `limit` | no | — | — |
| `changed` | no | — | — |
| `input_budget` | no | — | — |
| `risk` | no | — | — |
| `graph_nodes` | no | — | seed nodes for graph-aware ranking |
| `prev_pack` | no | — | previous pack hash — delta-aware dedup |
| `allow_escalate` | no | — | pack: escalate beyond budget instead of refusing |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## uninstall

### `uninstall`

**para que:** remove owned Platform Forge assets safely

- **por que:** remove só o que o manifesto declara como gerenciado
- **quando usar:** desinstalar sem deixar órfãos nos hosts

**Syntax**

```text
platformforge uninstall [help] [json] [FILE] [detail_level] [offline] [strict] [repo] [purge]
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `purge` | no | — | — |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## upgrade

### `upgrade`

**para que:** upgrade managed portable assets

- **por que:** atualiza a distribuição instalada
- **quando usar:** manter o runtime instalado em dia

**Syntax**

```text
platformforge upgrade [help] [json] [FILE] [detail_level] [offline] [strict] [repo] [profile] [host] [dry_run]
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `profile` | no | — | — |
| `host` | no | — | — |
| `dry_run` | no | — | — |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->

## workspace

### `workspace`

**para que:** workspace lifecycle and multi-repo manifest

- **por que:** workspace virtual: registra repos independentes sob workspace.yaml
- **quando usar:** orquestrar vários repos num escopo declarado

**Syntax**

```text
platformforge workspace [help] [json] [FILE] [detail_level] [offline] [strict] [repo] <workspace_cmd> [path] [name] [profile] [host]
```

| argument/flag | required | default | description |
|---|---|---|---|
| `help` | no | — | show this help message and exit |
| `json` | no | — | structured output (default) |
| `FILE` | no | — | write result to FILE |
| `detail_level` | no | — | summary|normal|full payload bounding |
| `offline` | no | — | forbid any network-capable adapter |
| `strict` | no | — | unresolved/refusals -> exit code 2 |
| `repo` | no | — | workspace/repo root |
| `workspace_cmd` | yes | — | — |
| `path` | no | — | — |
| `name` | no | — | — |
| `profile` | no | — | — |
| `host` | no | — | — |

<!-- keep:start -->
_free notes — errors, examples, next steps (hand-written, preserved)_
<!-- keep:end -->
