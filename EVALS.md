# EVALS — Forge Lab & the eval corpus

Two layers, different jobs:

- **Forge Lab** (`lab/scenarios/<id>/fixture` + `expected.yaml`) —
  end-to-end `analyze → judge` scenarios; `lab run-all` compares
  expected vs observed by rule prefix.
- **Eval corpus** (`evals/cases/<id>/case.yaml` + `fixture/`) — typed
  assertions over the same machinery, with variants.

## Eval types (§123)

`unit, integration, golden, contract, property, metamorphic, regression,
recall, precision, token_economy, graph_correctness, routing, security,
knowledge, version`.

A case declares `analyzer`, `fixture`, `expect.rules_fired` /
`rules_not_fired`, optional `versions` (product version map for gated
rules) or `expect.sources` (knowledge cases).

## Variants per rule (§121)

positive, negative, boundary, unresolved, version — coverage is reported
per variant by `evals coverage`; `uncovered` rules are named.

## Lab profiles (§118) + safety (§119)

`static` (default, offline fixtures) · `container` · `kubernetes` ·
`cloud`. Non-static profiles are refused without `--allow-profile` and a
safety contract (credentials, region/context, budget, cleanup).

## Chaos (§93/§120)

`lab chaos <dir>` — deterministic fault injection over the graph
(`environment: simulation`); production targets refused without
`--allow-prod`. Container/K8s chaos is lab-only by contract.

## Current corpus

34 eval cases, 13 lab scenarios, coverage 63/63 rules, precision
measured against negative/boundary corpus (§127). Coverage is evidence
of exercise — not a correctness proof.
