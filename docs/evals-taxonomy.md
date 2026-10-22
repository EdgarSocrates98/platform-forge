# Evals taxonomy — install-2.0 §7 (lf-0038)

Inventário classificado do corpus de avaliação desta forja. Fonte única:
`platformforge/evals/taxonomy.py` — servida por
`platformforge evals list --classified | describe | run | result` e
persistida no manifesto `forge/context/v1` (`eval_suites[].kind` +
`capabilities.evals.detail`).

## As 4 categorias (§7.1)

| Categoria | O que prova |
|---|---|
| `developer` | qualidade interna — corpus de desenvolvimento, tipos internos |
| `runtime-decision` | decisões do runtime — routing, fanout, agents esperados |
| `output-verification` | o contrato do resultado — vereditos do judge, corpora, lab |
| `host-conformance` | conformidade de host — replay de envelopes de superfície live |

## Inventário

| Suite | Categoria | Ambiente | Selada | Runner |
|---|---|---|---|---|
| `golden-verdicts` | output-verification | deterministic | sim | `evals run --type golden\|regression` (25 cases) |
| `agent-runtime` | runtime-decision | deterministic | sim | `evals run --type agent` (10 cases) |
| `live-replay` | host-conformance | deterministic | sim | `evals run --type live` (44 cases — envelopes gravados, nunca host vivo) |
| `internal-quality` | developer | deterministic | sim | `evals run --type <interno>` (9 cases) |
| `qpt-bench` | output-verification | deterministic | sim | `evals run --cases evals/qpt-bench` (6 suites) |
| `holdout` | output-verification | deterministic | sim | `cases replay --tier holdout` (6 cases, retido, nunca ajustado) |
| `golden-corpus` | developer | deterministic | sim | `cases replay --tier golden` (corpus de desenvolvimento) |
| `lab-scenarios` | output-verification | simulated | não | `lab run-all --profile static` (45 cenários) |

Contagem: developer=2, runtime-decision=1, output-verification=4,
host-conformance=1 — 8 suites sobre 94 cases + 6 benchmarks + 12 corpora
+ 45 cenários.

## Ops §7.2 → verbos reais

| Op conceitual | Verbo |
|---|---|
| `evals.list` | `platformforge evals list --classified` |
| `evals.describe` | `platformforge evals describe --suite <id>` |
| `evals.run` | `platformforge evals run --suite <id>` |
| `evals.result` | `platformforge evals result --suite <id>` (corpora: scorecard ancorado em `corpus_hash`) |
| `verification.plan` | `platformforge change propose --patch <diff>` |
| `verification.run` | `platformforge change verify --patch <diff>` |

Os seis ops são publicados como `discovery.commands` nomeados —
`discovery.ops` é o vocabulário fechado do §6.2 (`_forgecontext.py`
canônico, outro dono) e permanece inalterado. O verbo `capabilities`
expõe o mesmo mapa em `evals.ops`.

## Postura §7.3

- **Gabarito selado nunca sai**: `list`/`describe` emitem metadados +
  `integrity.suite_sha256`; runs ecoam vereditos, nunca blocos `expect:`
  ou `expected_known_truth`. `tests/test_evals_surface.py` prova por
  grepping de fatias reais das respostas.
- **Baselines protegidas por hash**: cada suite publica sha256 agregado;
  `cases replay` ancora o corpus em `corpus_hash`; ledgers FP/FN ficam em
  `.platformforge/ledgers/` versionado.
- **Simulado ≠ real**: todo resultado carrega `environment` e
  `real_environment_proof`; `live-replay` é evidência sobre replay
  determinístico, nunca prova de host vivo.
- **`unresolved` nunca vira pass**: vereditos unresolved ficam explícitos
  nos contadores — a regra §94 do runner já tratava tipo desconhecido
  como `unresolved`, e a superfície preserva isso.

## §7.4 — plan → run → evidence

`change propose` emite a proposta com o plano do sandbox;
`change verify` executa a verificação read-only do delta e grava o
recibo; `change review` é a pipeline completa. `approve`/`apply`
permanecem fronteira de host — o core recusa com unlock nomeado.

## §7.5 — contrato de agents

O roster canônico é `platformforge/agents/roster.py`; os mirrors de host
(`.claude/agents/`, `.agents/agents/`, `.codex/agents/`) são gerados por
`platformforge agents sync` e verificados por `agents lint` — texto de
protocolo nunca é duplicado nos mirrors.
