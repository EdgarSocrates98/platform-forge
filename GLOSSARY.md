# GLOSSARY — the Platform Forge vocabulary

Terms below are load-bearing: they appear in output payloads, findings,
receipts and refusal objects, and each has a defined meaning in code.

## Evidence

| Term | Meaning |
|---|---|
| `Fact` | An anchored, deterministic observation (`kind`, `source`, `location`, `tier`, `attrs`, `provenance`, `freshness`). Carries no judgment. |
| `EvidenceTier` T0–T7 | T0 measured-runtime · T1 provider-observed · T2 generated-plan · T3 repo-config · T4 official-doc · T5 operator-declared · T6 llm-inference · T7 conjecture. **T6/T7 cannot become facts** (`Fact.__post_init__` refuses). |
| `Finding` | Judgment over facts: `rule_id` + non-empty `evidence` (fact_ids) + `status` (`passed|violated|skipped`) + `attrs.sources` from the rule. Invalid by construction without evidence. |
| `provenance` | On edges: `observed · planned · declared · inferred`. Generated plans (T2) produce `planned`, never `observed` (ADR-0004). |
| `confidence` | 0.0–1.0 on edges/inferences; cross-repo joins are `inferred` with confidence < 1. |
| `state` (node) | Resolved from the strongest contributing fact: observed > planned > desired > inferred. |
| `version_notes` | On a finding when a version gate evaluated as unknown — `platform.version.unresolved:<product>(<constraint>)`. |

## Refusals & unknowns

| Term | Meaning |
|---|---|
| `refusal` | Named non-answer: `{refusal: <PF-*> code, unlock: <what would answer it>}`. Exit code ≥ 2 where applicable. |
| `unresolved` | A declared unknown — data exists but is insufficient/contradictory/version-gated. Never collapsed to zero or "low risk". |
| `state.contradiction` | Fact kind emitted when declared ≠ observed for the same field (e.g. tf says `public=false`, AWS says `public=true`). Both states are preserved. |
| `ownership.conflicted` | Ownership signals disagree (CODEOWNERS vs Backstage vs tags). Signals are claims — surfaced, never averaged. |
| `overclaimed` | Maturity v2 marker: declared signal outran observed evidence. |

## Economy

| Term | Meaning |
|---|---|
| `ContextPack` | Bounded token/context bundle with an evidence manifest — what was included, dropped, and why (rank reasons). |
| `payload_bytes` | Measured bytes of a tool call — the only thing the ledger counts. |
| `provider_tokens` | Never inferred from bytes. `tokens_unresolved` unless a host transcript supplies them. |
| `quality_per_token` | `evidence_preserved / tokens_spent`, measured on a same-task baseline — never a global ratio claim (ADR-0008). |
| `redaction_receipt` | Record of redaction count + labels (never values) at a boundary. |

## Rules & evals

| Term | Meaning |
|---|---|
| `rule` | Declarative predicate over facts: `applies_to` + `when` + `severity` + `sources` (registry-linked) + optional `versions`. |
| `version gate` | `rule.versions: {product: constraint}` — `True` applies, `False` skipped-with-reason, `None` → `version_notes` (ADR-0007). |
| `eval case` | `evals/cases/<id>/case.yaml` + `fixture/` — typed assertion (`golden`, `contract`, `version`, `knowledge`, `token_economy`, …). |
| `Lab scenario` | `lab/scenarios/<id>/fixture` + `expected.yaml` — end-to-end `analyze→judge` expectation. |
| `coverage` | Rule↔case mapping per variant (positive/negative/boundary/unresolved/version). Exercise evidence, not correctness proof. |
| `precision` | Measured false-positive rate on the negative/boundary corpus — bounded by corpus size, reported as such. |

## Change & risk

| Term | Meaning |
|---|---|
| `change review` | Read-only pipeline: sandbox copy → patch → before/after analysis → semantic graph delta → findings delta → risk → validation plan. `approve|apply` refuse in core. |
| `blast radius` | Impact classes reported separately: `direct · transitive · runtime · security · reliability · cost · compliance · unknown`. |
| `remediation plan` | `platformforge.remediation/v2`: ordered steps + `depends_on` DAG; steps without evidence are `refused`; execution is host-side. |
| `chaos` | Deterministic fault injection on the graph — `environment: simulation`; production targets refused without `--allow-prod`. |

## Interop

| Term | Meaning |
|---|---|
| `capability` | Registry v2 contract: id, version, domain, schemas, risk, offline, mutable, evidence_required, cost_class, agent_requirements, detail_levels. |
| `capability manifest` | `platformforge/capability-manifest/v2` — machine-readable surface for sibling forges (quality level, maturity, supported versions). |
| `artifact://sha256/<hash>` | Content-addressed ref returned when an MCP/CLI output exceeds its bound — payload lives in the artifact store. |
| `workspace member` | Repo in `workspace.yaml` with a role (`application|infrastructure|gitops|platform`); facts are tagged `workspace_member`. |
| `receipt` | Per-operation record: inputs, hashes, tools, versions, facts, findings, sources, cost, timing. Deterministic IDs enable replay. |
