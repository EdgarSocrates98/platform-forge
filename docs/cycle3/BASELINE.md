# Cycle 3 — Baseline (state of `main`)

Captured at CYCLE-3 kickoff. All numbers measured, not estimated.
Regenerate with the commands at the bottom before citing.

## Posture of `main`

| Signal | Value |
|---|---|
| Branch | `main` (tracks `origin/main`) |
| Tests | 260 passed, 0 failed (`uv run pytest`) |
| Lint | `uv run ruff check .` — clean |
| Docs drift | `tests/test_docs_drift.py` — pass |
| Lab | `lab run-all` — all static scenarios pass |
| Evals | `evals run` — all cases pass |
| Core LOC | ~13.9k (`platformforge/*.py`, 128 files) |
| Rules | 63 catalog rules |
| MCP tools / capabilities | 27 |
| Graph vocab | 51 node kinds, 27 edge kinds |
| Eval cases | 39 |
| Lab scenarios | 14 (all `static` profile) |
| Knowledge packs | aws, crossplane, kubernetes, terraform |
| Remote CI | externally blocked (billing) — `scripts/validate.py` is the local source of truth |

## Architecture baseline

**Epistemic pipeline** (unchanged since Cycle 1, hardened in 2/2.1):

```
Artifact → Evidence → Facts → Graph → Rules → Findings → Reasoning → Recommendation
```

- `EvidenceTier` T0–T7 (`models/base.py`); T6/T7 can never become `Fact`.
- `provenance ∈ {observed, planned, declared, inferred}` on graph edges.
- `Refusal` carries `PF-*` code + `unlock`; `--strict` promotes unresolved
  to exit 2.
- Redaction is a boundary pipeline (`core/redaction.py`) — applied before
  persistence/context/MCP.
- ArtifactStore is content-addressed under `.platformforge/store/`.
- Multi-repo via `workspace.yaml` fan-out (`§126`).

**What exists today (pre-Cycle-3):**

- Static analysis: Terraform/OpenTofu (HCL/plan/state), K8s manifests,
  Helm/Kustomize, GitOps (Argo/Flux), GH Actions, GitLab CI, Crossplane,
  Backstage catalog, Kyverno, cosign/SLSA/SBOM, supply chain.
- Cloud dumps: `analyze cloud-aws|azure|gcp` over collected API dumps
  (read-only, dump-driven — **no live collection**).
- Hubble flow dumps → facts (`analyze hubble`); OTel correlation
  (`correlate`), Prometheus/Grafana ingest, SLO/error budget, incident +
  postmortem v2, capacity, DR.
- Graphfy: facts → provenanced graph; snapshots under
  `.platformforge/graph/`; `graph diff` between snapshots; identity path
  queries.
- Economy: TokenSave index/packs/delta/ledger, RTK, Caveman, QPT bench,
  routing, economy report.
- Change lifecycle: `change propose|sandbox|verify|review|approve|apply`
  — `approve|apply` refused in core (host-side boundary).
- MCP: thin adapter over the same handlers; capability manifest v2 for
  Forge interop; agent roster with host mirrors.
- SDD: per-feature lifecycle under `.platformforge/sdd/<FEATURE>/`.

## The gap Cycle 3 closes

Today the platform understands `DECLARED` (git/manifests/IaC) and
`PLANNED` (tfplan). "Observed" exists only as provider *dumps* a human
collected — no observation model, no freshness/coverage semantics, no
runtime layer, no reconciliation engine, no temporal graph, no
multi-cluster identity.

Cycle 3 adds the `OBSERVED` (T1) and `RUNTIME` (T0) layers as
first-class evidence with explicit scope/coverage/freshness, keeps
absence-unless-proven semantics, and builds reconciliation + incident
intelligence on top — read-only, offline-first, dump-replayable.

## Non-negotiables carried forward

1. Offline core: no provider SDK, no LLM SDK, no network in the
   deterministic core. Live adapters are the only network boundary and
   must be transport-pluggable (fixture replay always works).
2. Read-only collectors: no create/update/delete/apply/exec/port-forward.
3. Credentials live in the host (aws CLI profile chain, kubeconfig) —
   never serialized, stored, logged, or sent over MCP/A2A.
4. Absence in an observation is not proof of non-existence.
5. No `runtime` provenance — runtime = `T0` + `observed` +
   `source_type=runtime` (§4 of the cycle spec).
6. Honest gaps: partial/stale/sampled coverage is reported, never hidden.

## Baseline reproduction

```bash
uv run pytest -q && uv run ruff check .
uv run pytest tests/test_docs_drift.py
uv run platformforge lab run-all && uv run platformforge evals run
uv run platformforge forge manifest --detail-level full
```
