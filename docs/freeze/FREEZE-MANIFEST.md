# FREEZE-MANIFEST

Generated from live registries — `platformforge freeze manifest`.

- freeze_start_sha: `2d874d9f7686c50dba3e8b4588eca4a2c6c39c97`
- lifecycle state: **dogfooding** (open-development → freeze-candidate → architecture-frozen → dogfooding → release-candidate → stable)
- python: 3.12.3 (supported: python 3.10, python 3.11, python 3.12, python 3.13)

## Surfaces

- public schemas: 21 (contracts/*.schema.json)
- CLI verbs: 49 — agents, ai, analytics, analyze, bench, capability, caveman, change, collect, context, correlate, diagnose, diff, doctor, drift, economy, evals, explain, federation, finops, fleet, forge, freeze, graph, impact, init, inspect, integrate, judge, knowledge, lab, live, mcp, observe, ops, optimize, plan, policy, product, recommend, reliability, risk, route, rtk, sdd, security, status, store, tokens
- MCP tools: 34
- capabilities: 34
- agents: 41 (coordinator:5, critic:1, executor:8, guardian:1, orchestrator:1, planner:1, referee:1, reviewer:7, specialist:15, verifier:1)
- knowledge packs: aws, crossplane, kubernetes, terraform (2 registered sources)

## Stability labels

**stable**

- fact/finding/graph contracts
- judge rule engine
- graphfy query surface
- change sandbox review
- tokensave/economy
- lab + evals harness
- MCP server

**experimental**

- agentic runtime (router v2, coordinators, debate)
- fleet analytics + optimization engine
- federation export
- ai platform awareness
- connected live collectors

**internal**

- sdd lifecycle machinery
- forge interop envelope
- freeze governance (this module)

## Known gaps

- agent benchmarks are router projections, not measured model spends
- analytics store is single-node SQLite (no concurrent writers)
- graph scale beyond 10k nodes / 500k edges is unsupported-on-host here
- no production evidence — nothing is production-validated
- connected (AWS/k8s) validation requires host credentials — offline by default

## Production-unvalidated claims

- every capability — no production telemetry exists in this repo
