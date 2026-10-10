# CLI SURFACE — generated reference

Machine-generated from `build_parser()` — every verb, subcommand and
flag, exhaustively. Regenerate with
`python scripts/gen_cli_surface.py --write`; the docs-drift test fails
if this file is stale. For the curated guide with examples see
[../CLI-REFERENCE.md](../CLI-REFERENCE.md).

Global flags on every verb: `--json` · `--output <file>` ·
`--detail-level summary|normal|full` · `--offline` · `--strict`.

## `agents`

- `agents` <path> (default '')  
  `--repo <v> — workspace/repo root (default '.')` · `--name <v> (default '')` · `--domain <v> (default '')`
- `agents bench`
- `agents check`
- `agents lint`
- `agents list`
- `agents playbook`
- `agents referee`
- `agents sync`

## `ai`

- `ai` <path> — yaml input (resources / capacity doc) (default '')  
  `--repo <v> — workspace/repo root (default '.')` · `--cost <v>` · `--denominators <v> — JSON {tokens,inferences,gpu_hours} (default '')`
- `ai economics`
- `ai gpu`
- `ai workloads`

## `analytics`

- `analytics` <path> (default '')  
  `--repo <v> — workspace/repo root (default '.')` · `--id <v> — metric id (default '')`
- `analytics maturity`
- `analytics metric`
- `analytics summary`

## `analyze`

- `analyze` <path> (default '.')  
  `--repo <v> — workspace/repo root (default '.')` · `--facts <v> — facts doc for ownership/contradiction joins (default '')` · `--config <v> (default '')` · `--state <v> (default '')` · `--vulns <v> — offline vuln list JSON (default '')` · `--kyverno-version <v> — declared kyverno version for deprecation checks (default '')`
- `analyze catalog`
- `analyze cloud-aws`
- `analyze cloud-azure`
- `analyze cloud-gcp`
- `analyze contradictions`
- `analyze cosign`
- `analyze crossplane`
- `analyze drift`
- `analyze gha`
- `analyze gitops`
- `analyze helm`
- `analyze hubble`
- `analyze iac`
- `analyze iam`
- `analyze k8s`
- `analyze kustomize`
- `analyze kyverno`
- `analyze ownership`
- `analyze plan`
- `analyze sbom`
- `analyze secrets`
- `analyze slsa`
- `analyze state`
- `analyze supply`

## `bench`

- `bench`  
  `--repo <v> — workspace/repo root (default '.')` · `--repeat <v> (default 3)` · `--sizes <v> — comma list for scale bench (default 50,200,800)` · `--edges <v> — comma list for edge sweep (default 100000,250000,500000)` · `--events — also run the analytics store event sweep (10k/100k/1M)`
- `bench run`
- `bench scale`
- `bench tokens`

## `cache`

- `cache`  
  `--repo <v> — workspace/repo root (default '.')` · `--layer <v> (default 'fact')` · `--key <v> (default '')` · `--scope <v> (default '')` · `--deps <v> (default '')` · `--dep <v> (default '')` · `--value <v> (default '')`
- `cache gc`
- `cache inspect`
- `cache invalidate`
- `cache stats`

## `capability`

- `capability`  
  `--repo <v> — workspace/repo root (default '.')` · `--name <v> (default '')` · `--domain <v> — §139 — domain to negotiate, e.g. k8s (default '')` · `--version <v> — §139 — product version to check support for (default '')`
- `capability check`
- `capability describe`
- `capability list`
- `capability manifest`

## `cases`

- `cases` <path> (default '')  
  `--repo <v> — workspace/repo root (default '.')` · `--tier {golden|holdout} (default '')` · `--out <v> — challenger routing.yaml for route-bench (default '')` · `--stamp — context-audit: write measured context_cost back into case.yaml`
- `cases context-audit`
- `cases ledger`
- `cases ledger-check`
- `cases list`
- `cases replay`
- `cases route-audit`
- `cases route-bench`
- `cases template`
- `cases validate`

## `caveman`

- `caveman` <file> — file to compress ('-' = stdin)  
  `--repo <v> — workspace/repo root (default '.')` · `--mode {off|lite|full|auto} (default 'lite')` · `--context-risk <v> (default 'normal')`

## `change`

- `change`  
  `--repo <v> — workspace/repo root (default '.')` · `--patch <v> — unified diff file (default '')` · `--file <v> — rel/path=src-file (or literal content)` · `--signals <v> — JSON risk signals doc (review only) (default '')`
- `change apply`
- `change approve`
- `change propose`
- `change review`
- `change sandbox`
- `change verify`

## `collect`

- `collect` <path> (default '')  
  `--repo <v> — workspace/repo root (default '.')`

## `context`

- `context`  
  `--repo <v> — workspace/repo root (default '.')` · `--task <v> (default '')` · `--input-budget <v>` · `--changed <v>` · `--scope <v> (default 'repository')` · `--budget-bytes <v>` · `--essential-bytes <v>` · `--required <v>` · `--role <v> (default 'specialist')` · `--facts <v> (default '')` · `--findings <v> (default '')` · `--rules <v>` · `--knowledge <v>` · `--graph-refs <v>` · `--questions <v>` · `--ref <v> (default '')` · `--section <v> (default '')`
- `context capsule`
- `context delta`
- `context expand`
- `context gc`
- `context inspect`
- `context pack`

## `correlate`

- `correlate` <path>  
  `--repo <v> — workspace/repo root (default '.')`

## `diagnose`

- `diagnose` <node>  
  `--repo <v> — workspace/repo root (default '.')` · `--findings <v> (default '')` · `--facts <v> (default '')`

## `diff`

- `diff`  
  `--repo <v> — workspace/repo root (default '.')` · `--before <v>` · `--after <v>`

## `doctor`

- `doctor`  
  `--repo <v> — workspace/repo root (default '.')` · `--deep — §141 contract checks (config, manifest, knowledge, parity, index, store)`

## `drift`

- `drift`  
  `--repo <v> — workspace/repo root (default '.')` · `--config <v>` · `--state <v>`

## `economy`

- `economy`  
  `--repo <v> — workspace/repo root (default '.')` · `--signal <v> — JSON TaskSignal (strategy/compare) (default '')` · `--path <v> — facts doc for qpt (default '')` · `--task <v> (default 'analysis')` · `--input-budget <v>` · `--versions <v> — JSON product versions for qpt, e.g. '{"kubernetes": "1.29"}' (default '')` · `--run-id <v> (default '')` · `--spent <v> — JSON spent budget (checkpoint) (default '')` · `--remaining <v> — JSON remaining budget (default '')` · `--deps <v> — JSON dep hashes (checkpoint) (default '')` · `--profile <v> — routing profile (resume) (default '')` · `--planned <v> — JSON planned usage (reconcile) (default '')` · `--observed <v> — JSON observed usage (reconcile) (default '')`
- `economy checkpoint`
- `economy compare`
- `economy doctor`
- `economy explain`
- `economy qpt`
- `economy qpt-bench`
- `economy reconcile`
- `economy report`
- `economy resume`
- `economy strategy`

## `evals`

- `evals`  
  `--repo <v> — workspace/repo root (default '.')` · `--type <v> (default '')` · `--cases <v> (default '')`
- `evals coverage`
- `evals list`
- `evals precision`
- `evals run`

## `explain`

- `explain` <path> — findings doc (json)  
  `--repo <v> — workspace/repo root (default '.')` · `--name <v> — finding_id or rule_id (default '')` · `--facts <v> — facts doc (json) (default '')`

## `federation`

- `federation` <path> — payload yaml (export) (default '') <question> — fleet question (query) (default '')  
  `--repo <v> — workspace/repo root (default '.')` · `--nodes <v> — fleet dirs (query) (default [])` · `--classification <v> (default '')` · `--manifest <v> (default '')` · `--node-id <v> (default '')` · `--capabilities <v> (default '')` · `--freshness <v> (default '')` · `--limit <v> (default 0)`
- `federation export`
- `federation manifest`
- `federation query`

## `finops`

- `finops` <path> (default '')  
  `--repo <v> — workspace/repo root (default '.')` · `--by <v> (default 'cost_center')` · `--denominators <v> — JSON {unit: measured_count} for `finops unit` (default '')`
- `finops allocate`
- `finops costs`
- `finops focus`
- `finops focus-validate`
- `finops graph`
- `finops ingest`
- `finops report`
- `finops unit`

## `fleet`

- `fleet` <path> — fleet dir (lab/fleets/acme shape) (default '')  
  `--repo <v> — workspace/repo root (default '.')` · `--question <v> — risks: run a single fleet question (default '')` · `--limit <v> (default 0)` · `--window <v> — drift window (24h/7d/30d/90d) (default '')`
- `fleet capacity`
- `fleet costs`
- `fleet coverage`
- `fleet drift`
- `fleet golden-path`
- `fleet graph`
- `fleet incidents`
- `fleet list`
- `fleet operations`
- `fleet policies`
- `fleet recommendations`
- `fleet report`
- `fleet risks`
- `fleet status`

## `forge`

- `forge` <path> (default '')  
  `--repo <v> — workspace/repo root (default '.')` · `--name <v> (default '')` · `--src <v> (default '')` · `--dst <v> (default '')`
- `forge collect`
- `forge delegate`
- `forge discover`
- `forge manifest`
- `forge verify`

## `freeze`

- `freeze` <path> (default '')  
  `--repo <v> — workspace/repo root (default '.')` · `--out <v> (default '')` · `--spec <v> — FeatureException JSON for `freeze exception` (default '')`
- `freeze check`
- `freeze exception`
- `freeze manifest`
- `freeze snapshot`

## `graph`

- `graph` <facts> (default '')  
  `--repo <v> — workspace/repo root (default '.')` · `--node <v> (default '')` · `--src <v> (default '')` · `--dst <v> (default '')` · `--before <v> (default '')` · `--after <v> (default '')` · `--at <v> — at: ISO timestamp (default '')` · `--edge-id <v> — timeline: edge id (default '')` · `--source-type {desired|planned|observed|runtime} — §6 snapshot type for `graph build` (default 'desired')` · `--no-browser — graph ui: serve without opening a browser (SSH/remote)` · `--port <v> — graph ui: port (default ephemeral) (default 0)` · `--snapshot <v> — graph view: emit the view of a saved snapshot hash (default '')`
- `graph at`
- `graph blast`
- `graph build`
- `graph cycles`
- `graph dependents`
- `graph deps`
- `graph diff`
- `graph gaps`
- `graph identity-access`
- `graph identity-become`
- `graph identity-blast`
- `graph identity-workloads`
- `graph paths`
- `graph snapshots`
- `graph stats`
- `graph timeline`
- `graph ui`
- `graph view`

## `impact`

- `impact`  
  `--repo <v> — workspace/repo root (default '.')` · `--node <v>`

## `init`

- `init`  
  `--repo <v> — workspace/repo root (default '.')` · `--name <v> (default '')`

## `inspect`

- `inspect`  
  `--repo <v> — workspace/repo root (default '.')`

## `install`

- `install`  
  `--repo <v> — workspace/repo root (default '.')` · `--profile <v> — minimal|recommended|full (contract) or native profile name (default 'recommended')` · `--host {agents|claude|codex|devin|copilot|all}` · `--scope {project|workspace|user} (default 'project')` · `--yes, -y — explicit approval — required for writes` · `--purge — uninstall: also remove .platformforge state` · `--to <v> — update: pinned version — never 'latest'` · `--components <v> — optional components csv: skills,agents,mcp,tui,graph-studio` · `--dry-run`
- `install apply`
- `install doctor`
- `install mcp-verify`
- `install repair`
- `install status`
- `install uninstall`
- `install update`

## `integrate`

- `integrate`  
  `--repo <v> — workspace/repo root (default '.')` · `--host {claude|codex|devin|copilot|generic}` · `--detach`

## `judge`

- `judge` <facts>  
  `--repo <v> — workspace/repo root (default '.')` · `--catalog <v>` · `--versions <v> — JSON product versions, e.g. '{"kubernetes": "1.29"}' (default '')`

## `knowledge`

- `knowledge`  
  `--repo <v> — workspace/repo root (default '.')`
- `knowledge check`
- `knowledge contract`
- `knowledge drift`
- `knowledge packs`

## `lab`

- `lab` <path> (default '')  
  `--repo <v> — workspace/repo root (default '.')` · `--allow-prod — chaos: allow env:production targets` · `--profile {static|container|kubernetes|cloud} — §118 lab profile filter (default '')` · `--allow-profile — §119 — opt into non-static lab profiles`
- `lab chaos`
- `lab list`
- `lab run`
- `lab run-all`

## `live`

- `live`  
  `--repo <v> — workspace/repo root (default '.')` · `--provider {kubernetes|aws} (default 'kubernetes')` · `--region <v> — aws: restrict regions (repeatable)` · `--service <v> — aws: restrict services (repeatable)` · `--deep — doctor: probe every provider adapter` · `--context <v> — kube context (default '')` · `--namespace <v> — restrict to namespace (repeatable)` · `--resource-type <v> — restrict resource types (repeatable)` · `--selector <v> — k8s label selector (default '')` · `--namespaced-only — rbac: emit Role instead of ClusterRole` · `--no-store — snapshot: emit envelope without persisting` · `--desired <v> — reconcile: facts.json path (default: repo scan) (default '')` · `--planned <v> — reconcile: planned facts.json path (default '')` · `--observed <v> — reconcile: observation_id or envelope.json (default '')` · `--no-observed — reconcile: desired↔planned only` · `--otel <v> — topology: OTLP spans json (default '')` · `--hubble <v> — topology: hubble flows (default '')` · `--slices <v> — topology: endpointslices json (default '')` · `--apply-to-graph — topology: persist runtime edges into graph` · `--register <v> — clusters: register cluster JSON spec (default '')` · `--before <v> — drift: obs id/file (default '')` · `--after <v> — drift: obs id/file (default '')` · `--incident <v> — incident: incident JSON {timestamp,resources} (default '')` · `--changes <v> — incident: candidate changes JSON list (default '')` · `--events-file <v> — changes: append ChangeEvents from JSON file (offline-safe) (default '')` · `--collect — changes: collect via provider adapter (host-side)` · `--gc — changes: garbage-collect the change journal` · `--since <v> — changes: events after ISO ts (default '')` · `--until <v> — changes: events before ISO ts (default '')` · `--resource <v> — changes: filter by resource id (default '')` · `--events <v> — incident: timeline events JSON list (default '')` · `--window <v> — incident: correlation window seconds (default 3600)` · `--drift-events <v> — plan: drift events JSON (default: diff latest two stored observations) (default '')` · `--max-objects <v> (default 0)` · `--max-api-calls <v> (default 0)` · `--max-bytes <v> (default 0)`
- `live capability`
- `live changes`
- `live clusters`
- `live doctor`
- `live drift`
- `live incident`
- `live plan`
- `live rbac`
- `live reconcile`
- `live required-permissions`
- `live snapshot`
- `live status`
- `live topology`

## `mcp`

- `mcp` <path> (default '')  
  `--repo <v> — workspace/repo root (default '.')` · `--name <v> (default '')` · `--input <v> (default '')` · `--host {claude|codex|devin|copilot|generic} (default 'generic')`
- `mcp call`
- `mcp detach`
- `mcp integrate`
- `mcp serve`
- `mcp tools`

## `observe`

- `observe` <path> (default '')  
  `--repo <v> — workspace/repo root (default '.')` · `--sli <v> — JSON {good,bad,total}_events (default '')` · `--windows <v> — JSON {window: {good,bad}} for slo-burn (default '')` · `--alerts <v> (default '')` · `--changes <v> (default '')` · `--incident <v> — incident JSON for postmortem (default '')` · `--facts <v> — facts JSON for dr (default '')` · `--window <v> (default 3600)`
- `observe capacity`
- `observe dr`
- `observe grafana`
- `observe incident`
- `observe otel`
- `observe postmortem`
- `observe prometheus`
- `observe semconv`
- `observe slo`
- `observe slo-burn`
- `observe timeline`

## `ops`

- `ops` <name_pos> — runbook id or 'list' (default '')  
  `--repo <v> — workspace/repo root (default '.')` · `--intent <v> — intent JSON file (default '')` · `--plan <v> — plan JSON/YAML file (default '')` · `--spec <v> — ops run spec YAML/JSON (default '')` · `--policies <v> — policies YAML list (default '')` · `--environment <v> (default 'unknown')` · `--level {S0|S1|S2|S3|S4|S5} (default 'S1')` · `--execute — real mutation — requires hash-bound approval + host transports; default is dry-run` · `--request <v> — delegate request JSON (default '')` · `--name <v> — runbook id (positional name overrides) (default '')` · `--bind <v> — runbook bind params JSON (default '')` · `--operation-id <v> (default '')` · `--post-rollback <v> — rollback: post-rollback observation JSON {step_id: {dim: value}} for verification (default '')` · `--resource <v> — history filter (default '')` · `--evidence-tier <v> — autorem-eval (default '')` · `--approval-id <v> (default '')` · `--subject-hash <v> — envelope/plan hash being approved (default '')` · `--subject-kind <v> (default 'execution-envelope')` · `--actor <v> — human identity (default '')` · `--actor-kind {human|agent|host|system} (default 'human')` · `--role <v> (default '')` · `--approval-type {automatic-policy|single-human|resource-owner|platform-owner|security-review|dual-human} (default 'single-human')` · `--expires-at <v> (default '')` · `--bounds <v> — parameter bounds JSON (default '')` · `--scope <v> — csv resource scope (default '')` · `--reason <v> (default '')`
- `ops analytics`
- `ops approve`
- `ops autorem-eval`
- `ops capabilities`
- `ops config`
- `ops delegate`
- `ops graph`
- `ops history`
- `ops intent`
- `ops plan`
- `ops policy-eval`
- `ops risk`
- `ops rollback`
- `ops run`
- `ops runbook`
- `ops simulate`
- `ops status`
- `ops store-list`
- `ops store-verify`

## `optimize`

- `optimize` <path> (default '')  
  `--repo <v> — workspace/repo root (default '.')` · `--id <v> — recommendation id (default '')` · `--out <v> — plan: write the ChangeIntent doc to this file (default '')` · `--limit <v> (default 0)`
- `optimize explain`
- `optimize list`
- `optimize plan`
- `optimize portfolio`
- `optimize scan`

## `plan`

- `plan` <path>  
  `--repo <v> — workspace/repo root (default '.')` · `--facts <v> (default '')`

## `policy`

- `policy` <path> (default '')  
  `--repo <v> — workspace/repo root (default '.')`
- `policy check`
- `policy list`

## `portable`

- `portable` <path> (default 'dist/platformforge-portable')  
  `--repo <v> — workspace/repo root (default '.')` · `--profile <v> (default 'agentic')` · `--host {agents|claude|codex|devin}` · `--offline-bundle`
- `portable build`
- `portable doctor`
- `portable install`
- `portable verify`

## `product`

- `product`  
  `--repo <v> — workspace/repo root (default '.')` · `--signals <v> — JSON signals doc (default '')` · `--findings <v> — findings JSON doc (default '')` · `--facts <v> — facts JSON for analysis (default '')` · `--id <v> — golden path id (default '')`
- `product backstage`
- `product capabilities`
- `product maturity`
- `product path`
- `product path-analyze`
- `product paths`
- `product scorecard`

## `recommend`

- `recommend` <path> — findings doc (json)  
  `--repo <v> — workspace/repo root (default '.')`

## `reliability`

- `reliability` <path> (default '')  
  `--repo <v> — workspace/repo root (default '.')`

## `risk`

- `risk`  
  `--repo <v> — workspace/repo root (default '.')` · `--node <v> — graph node id to assess (default '')` · `--signals <v> — JSON signals doc (default '')`

## `route`

- `route` <signal> — JSON TaskSignal  
  `--repo <v> — workspace/repo root (default '.')`

## `routing`

- `routing`  
  `--repo <v> — workspace/repo root (default '.')` · `--task <v> (default '')` · `--profile <v> (default 'balanced')` · `--risk <v> (default 'low')` · `--signal <v> (default '')` · `--estimated <v> (default '')` · `--champion <v> (default '')` · `--challenger <v> (default '')` · `--approved` · `--run-id <v> (default '')` · `--mode <v> (default 'deterministic')` · `--correctness <v>` · `--tokens <v>` · `--agents <v> (default 0)` · `--provider-calls <v> (default 0)`
- `routing compare`
- `routing explain`
- `routing scorecard`

## `rtk`

- `rtk` <file> — output file to compact ('-' = stdin) (default '-')  
  `--repo <v> — workspace/repo root (default '.')` · `--command <v> — command that produced output (default '')` · `--exit-code <v> (default 0)` · `--artifact <v> (default '')` · `--start <v>` · `--end <v>` · `--pattern <v>`
- `rtk compact`
- `rtk expand`

## `sdd`

- `sdd`  
  `--repo <v> — workspace/repo root (default '.')` · `--feature <v>` · `--body <v> — artifact body or JSON (default '')` · `--phase <v> — stamp single phase` · `--verify <v> — verify JSON for ship gate (default '')` · `--risk-accepted` · `--override` · `--override-reason <v> (default '')`
- `sdd build`
- `sdd check`
- `sdd contract`
- `sdd define`
- `sdd design`
- `sdd discover`
- `sdd init`
- `sdd learn`
- `sdd plan`
- `sdd review`
- `sdd ship`
- `sdd stamp`
- `sdd status`
- `sdd verify`

## `security`

- `security` <path> (default '')  
  `--repo <v> — workspace/repo root (default '.')`

## `status`

- `status`  
  `--repo <v> — workspace/repo root (default '.')`

## `store`

- `store`  
  `--repo <v> — workspace/repo root (default '.')` · `--keep-days <v> (default 30.0)` · `--execute — actually delete (default: dry-run)`
- `store gc`
- `store stats`

## `tokens`

- `tokens`  
  `--repo <v> — workspace/repo root (default '.')` · `--task <v> (default '')` · `--query <v> (default '')` · `--mode {literal|regex|symbol|path|kind} (default 'literal')` · `--limit <v> (default 20)` · `--changed <v>` · `--input-budget <v>` · `--risk {low|medium|high|critical}` · `--graph-nodes <v> — seed nodes for graph-aware ranking` · `--prev-pack <v> — previous pack hash — delta-aware dedup` · `--allow-escalate — pack: escalate beyond budget instead of refusing`
- `tokens delta`
- `tokens index`
- `tokens ledger`
- `tokens pack`
- `tokens search`
- `tokens stats`

## `uninstall`

- `uninstall`  
  `--repo <v> — workspace/repo root (default '.')` · `--purge`

## `upgrade`

- `upgrade`  
  `--repo <v> — workspace/repo root (default '.')` · `--profile <v> (default '')` · `--host {agents|claude|codex|devin}` · `--dry-run`

## `workspace`

- `workspace` <path> (default '.')  
  `--repo <v> — workspace/repo root (default '.')` · `--name <v> (default '')` · `--profile <v> (default 'agentic')` · `--host {agents|claude|codex|devin}`
- `workspace add`
- `workspace doctor`
- `workspace init`
- `workspace list`
- `workspace remove`
- `workspace status`

