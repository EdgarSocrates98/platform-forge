# FREEZE FINAL-MATRIX

Capability × (architecture maturity, validation level, scale evidence,
real-world evidence, known limits, freeze status).

Maturity ladder (P-scale, evidence-decided — never assigned by fiat):

| Level | Meaning |
|---|---|
| P0 | declared only |
| P1 | implemented |
| P2 | unit/integration validated |
| P3 | eval/lab validated |
| P4 | measured at scale + deterministic replay |
| P5 | production-validated on real workloads |

| Capability | Maturity | Validation | Scale evidence | Real-world evidence | Known limits | Freeze status |
|---|---|---|---|---|---|---|
| fact/finding contracts + provenance | P4 | suite + evals | — | self/cross-Forge dogfood (RW-1..3 fixed) | projections are lossy views, marked so | frozen/stable |
| rule engine + catalog (63 rules) | P4 | evals 93, lab 44+, replay 15/15 | — | corpus + dogfood FPs logged | fixture-scoping gap (RW-4); prose-secret FN risk (RW-5 note) | frozen/stable |
| Graphfy (graph/query/diff/identity/temporal) | P4 | graph evals + deterministic replay | `PERFORMANCE-RECEIPT.json`; unsupported sizes named | dogfood graphs on 3 forges | 100k-node graphs: measured but slow on host | frozen/stable |
| change sandbox review | P4 | hardening tests + SEC-1 containment fix | — | dogfood | `patch` binary dependency fails closed | frozen/stable |
| TokenSave/economy + context packs | P3 | economy evals + context-audit (0% unused) | context bytes measured per case | — | bench verdict: projection-only until observed ledger rows | frozen/stable |
| lab + eval harness | P4 | lab run-all + evals run green | — | replay corpus built on it | fleet scenarios grade differently than analyzer cases | frozen/stable |
| MCP surface | P3 | CLI≡MCP semantic tests, mirror parity 205 | — | — | versioned rules → `unresolved` over MCP (documented) | frozen/stable |
| agentic runtime (41 agents, Router V2) | P3 | agents gates + route/context audits + evals | routing audit 16 cases, fanout 3.38 | — | no observed production run-ledger yet → P4 pending dogfooding | frozen/experimental |
| fleet analytics + optimization | P3 | fleet scenarios + adversarial E1–E12 | — | — | no real-fleet pilot evidence | frozen/experimental |
| federation export | P2 | fail-closed export tests | — | — | never exercised against a second live node | frozen/experimental |
| AI platform awareness | P2 | unit tests + evals | — | — | denominator-required economics untested at fleet scale | frozen/experimental |
| connected live collectors | P2 | read-only transport refusal tests | — | — | dumps only; never calls provider APIs from core | frozen/experimental |
| SDD lifecycle machinery | P3 | hash-cascade + gate tests | — | used in-repo for cycles | internal tooling, not a product surface | frozen/internal |

## Reading the matrix

- No P5 cells — nothing has run against real production state. That is
  the honest ceiling at freeze close; the pilot path in LIFECYCLE.md
  (observe → recommend → prepare → governed mutate) is how P5 evidence
  gets earned.
- `experimental` labels match the freeze manifest's stability tiers —
  surfaces are contract-stable, evidence-thin.
- Architecture maturity (design coherence, boundaries, contracts) is
  assessed in ARCHITECTURE-FREEZE-REVIEW.md separately from this
  operational-readiness matrix — the two are deliberately not fused
  into one score.
