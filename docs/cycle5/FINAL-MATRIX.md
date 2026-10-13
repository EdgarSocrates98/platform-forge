# Cycle 5 — Final Matrix

Maturity levels: `foundation` → `partial` → `implemented` →
`validated` → `lab-validated` → `production-validated` (never
self-declared — no production evidence exists here, so nothing below
claims it).

| Capability | Before | After | Implementation | Tests | Evals | Lab | Benchmark | Evidence | Known Gap |
|---|---|---|---|---|---|---|---|---|---|
| Fleet contracts | none | Fleet/FleetMember/FleetSnapshot + coverage | `fleet/models.py`, `loader.py` | yes | member-key probe | fleet-partial | — | schema `fleet/v1` | live collectors are host-side |
| Org graph layers | technical only | 8 layers + org edges (`organizational` class) | `fleet/orggraph.py`, `graph/vocab.py` | yes | — | fleet-ownership | — | ADR-0032 | cross-layer paths are BFS-only |
| Fleet questions | none | 9 deterministic questions | `fleet/query.py`, `fleet risks` | yes | — | fleet-risk/golden-path/ownership | — | fact_ids cited | question set is fixed |
| History engine | per-verb queries | unified sources + windows + patterns | `analytics/history.py` | yes | window probes | fleet-recurring-incident | — | strict windows; stale can't seed | real-clock on CLI (lab pinned) |
| Platform measurement | scorecard v2 | per-dimension metrics + maturity V3 | `analytics/measurement.py` | yes | — | — | — | unknown ≠ 0 | self_service needs ticket data |
| Golden-path intel | adoption counts | friction/escapes/outcomes + recs | `analytics/goldenpath.py` | yes | — | fleet-golden-path | — | causal_claim: false | escape reasons enumerated set |
| Policy intelligence | decision log | metrics + FP candidates + recs | `analytics/policyintel.py` | yes | fp-candidate probe | fleet-policy-friction | — | evidence-gated | review-only, never auto-applies |
| FinOps V4 | v1 costs/alloc | hierarchy/trend/anomaly/idle/unit | `analytics/finops_v4.py` | yes | cost probes | fleet-cost | — | denominators required | no provider ingest live |
| Capacity | per-service SLO | fleet snapshots + risk + forecast | `analytics/capacity.py` | yes | — | fleet-capacity | — | unknown headroom stays | forecast = linear only |
| Reliability | incident v3 | profiles + hotspots + blast | `analytics/reliability.py` | yes | centrality≠crit probe | fleet-op-hotspot | — | MTTR needs real ts | blast concentration is degree-only |
| Ops analytics | ops store queries | metrics/hotspots/recurrence/timeline | `analytics/opsanalytics.py` | yes | — | fleet-op-hotspot | — | auto_remediate: false | — |
| Optimization | recommend (static) | opportunities→recs→ChangeIntent | `optimize/{engine,scan,models}.py` | yes | suppression probes | fleet recommendations | — | §303 boundary; E7 | effort always `unknown` (declared) |
| Federation | delegation contract | manifests + classified export + query | `federation/node.py` | yes | secret-denied probe | fleet-federation | — | fail-closed policy | transport is host-side |
| AI platform | none | GPU pools, MIG, serving, unit econ | `aiplat/` | yes | denominator probe | fleet-ai | — | unknown w/o denominators | no model-registry scope |
| DX metrics | none | team-level friction | `analytics/dx.py` | yes | no-person probe | — | — | FORBIDDEN_METRICS | needs richer inputs |
| Analytics store | in-memory | SQLite + retention + forget | `analytics/store.py` | yes | — | — | bench scale | forget receipt | single-node |
| Graph backend | memory only | pluggable + SQLite | `graph/backend.py` | yes | — | — | bench scale | parity tests | no network backends (by design) |
| Config v3 | v2 | features + privacy pins + migration | `ops/config.py` | yes | — | — | — | PF-OPS-CONFIG-* refusals | — |
| Lab/evals | 32 scenarios | +11 fleet scenarios, +14 probes | `lab/fleetlab.py`, `evals/fleet_invariants.py` | yes | 82 total | 43 total | — | deterministic clocks | L1–L4 tiers still host-gated |
| Adversarial | R1–R6 (4.1) | E1–E12 fleet review | `tests/test_fleet_adversarial.py` | 13 tests | — | — | — | bugs found & fixed | — |
| Validation | 22 gates | 33 gates (+11 fleet/adversarial) | `scripts/validate.py` | yes | — | — | — | receipt JSON | remote CI unverified here |
| CLI surface | 43 verbs | 48 verbs (+5 namespaces) | `cli/fleetcmd.py`, `main.py` | yes | — | — | — | read-only outputs | no MCP tools for new surfaces |
| Docs | — | 10 new + 9 updated + 10 ADRs | top-level *.md, `docs/adr/003*` | drift gate | — | — | — | docs-drift passes | FINOPS/SRE covered in-domain |

Everything in "After" is `validated` by gate + tests + lab where a
lab exists; rows without lab coverage are `implemented/validated`,
never overstated.
