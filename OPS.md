# OPS — Governed Platform Engineering Control Plane (Cycle 4)

Cycle 4 turns Platform Forge from an *intelligence* system (observe →
understand → diagnose → recommend) into a **governed control plane**:

```
OBSERVE → UNDERSTAND → DIAGNOSE → RECOMMEND → PLAN → SIMULATE
→ GOVERN → APPROVE → EXECUTE → VERIFY → CONVERGE / ROLLBACK
→ AUDIT → LEARN
```

Target autonomy: **A4 — execute with human approval**. A5 is restricted
to lab/non-production narrow reversible experiments; **A6 (closed-loop
autonomy) is a non-goal**.

```
A0 observe   A1 recommend   A2 plan   A3 prepare
A4 execute w/ human approval   A5 auto low-risk (lab)   A6 ✗
```

## Invariants (enforced, tested adversarially)

- **Typed actions only.** `ops/actions.py` is the vocabulary. Arbitrary
  commands (`shell.run`, `kubectl.exec`, `aws.call`, `eval`,
  `execute_anything`) refuse `PF-OPS-UNSTRUCTURED`. The core never
  receives a shell string.
- **Host boundary.** Executors translate typed actions → argv; the
  injected `Transport` runs them (`host_transport()` = argv-only
  `subprocess.run`, never `shell=True`). Without a transport, mutating
  actions refuse `PF-OPS-NO-TRANSPORT`. Dry-run never reaches the host.
- **Hash binding.** Approvals sign a canonical payload bound to the
  envelope hash; envelopes bind to the change-plan hash. Tampering,
  stale plans, wrong scope → refusal.
- **Human approval.** `check_approval` defaults to `actor_kind=human`;
  agent-minted approvals do not satisfy A4 unless the host widens the
  allowlist. TTL, scope, role, parameter bounds all checked.
- **Verification ≠ exit code.** `ops/verify.py` compares expected delta
  vs *observed* state across immediate/stabilization/extended windows +
  SLO contract. Command success is not convergence.
- **Prod safety.** Auto-rollback disabled in prod; auto-remediation
  requires all 12 eligibility checks; break-glass is scoped + expiring +
  audited.
- **Audit.** `OperationLedger` is append-only + hash-chained; the
  operation store persists operations + receipts under
  `.platformforge/operations/`; `ops store-verify` checks the chain.
- **Redaction.** Ledger entries and envelope action params pass through
  the boundary redaction pipeline — secrets never serialize.

## Pipeline objects

| Object | Module | Role |
|---|---|---|
| `ChangeIntent` | `ops/models.py` | why + who + evidence refs (no evidence → `PF-OPS-NO-EVIDENCE`) |
| `ChangePlan` | `ops/models.py` | typed `PlanStep` DAG + expected delta; hash-pinned |
| `SimulationResult` | `ops/simulate.py` | S0–S5 levels; deterministic projection receipt |
| risk R0–R5 | `ops/risk.py` | 12-dimension decomposition; unknown ≠ low |
| `Policy`/`PolicyDecision` | `ops/policy.py` | deny-overrides, exceptions w/ expiry, shadow mode |
| `Approval`/`BreakGlass` | `ops/approval.py` | hash-bound, TTL, scope, actor-kind, signature |
| `ExecutionEnvelope` | `ops/envelope.py` | binds plan hash + decisions + approvals + actions |
| `Operation`/`OperationLedger` | `ops/operation.py` | FSM + locks + append-only hash-chained ledger |
| verification | `ops/verify.py` | observed-delta windows + SLO → converged/regressed |
| `RollbackPlan` | `ops/rollback.py` | derived per action; saga compensation; prod≠auto |

## Typed action catalog

`ops capabilities` lists all actions with risk/mutation/dry-run/
idempotency/rollback metadata. Executors: `git`, `terraform`/`tofu`
(saved-plan hash binding + drift precheck), `argocd`, `kubernetes`
(narrow verbs only), `observe` (read-only collectors).

## Runbooks & Golden Paths

- `ops/runbook.py` — parameterized, hashed runbooks
  (`ops runbook list|show|--bind`), e.g. `replica-drift-restore`.
- `ops/goldenpath.py` — `PlatformRequest` lifecycle with staged
  receipts + readiness scoring.
- `ops/gates.py` — FinOps cost-delta + security gates in the pipeline.

## Operational graph

`ops/opgraph.py` projects intents/plans/envelopes/approvals/operations
into Graphfy as operational nodes/edges (`intends`, `planned_by`,
`mutates`, `approved_by`, `executed_by`, `verifies`, `rolled_back_by`,
`produced_receipt`) — impact class `operation`, kept distinct from
dependency edges so blast-radius semantics stay clean.

## Cross-Forge delegation

`ops/registry.py` + capability-manifest **v3**: sibling forges may
submit intents/plans for evaluation; delegation **never** carries
execution authority. `ops delegate --request f.json` validates.

## CLI

```
platformforge ops capabilities|config|delegate|intent|plan|simulate
                |risk|policy-eval|runbook|run|store-list|store-verify
```

`ops run --spec ops.yaml` runs the full governed pipeline on a spec
(same shape as lab fixtures). Without `--execute` every step is a
dry-run receipt; `--execute` attaches the host argv transport and still
requires a valid hash-bound approval. Results persist to the operation
store; every refusal preserves a `PF-*` code + unlock instruction.

## Refusal codes (selection)

| Code | Meaning |
|---|---|
| `PF-OPS-UNSTRUCTURED` | free-form/forbidden action verb |
| `PF-OPS-NO-TRANSPORT` | mutating step without host transport |
| `PF-OPS-NO-EVIDENCE` | intent/plan lacking evidence refs |
| `PF-OPS-NO-APPROVAL` | no approval satisfies the envelope hash |
| `PF-OPS-APPROVAL-EXPIRED` | approval TTL elapsed |
| `PF-OPS-ENVELOPE-UNGOVERNED` | envelope minted without policy decisions |
| `PF-OPS-PRECONDITION-FAILED` | stale observation / plan-hash drift / freeze |
| `PF-OPS-POLICY-BLOCK` | deny-overrides policy verdict |
| `PF-OPS-LOCK-CONFLICT` | resource already locked by an operation |
| `PF-OPS-RUNBOOK-UNKNOWN` | unknown runbook id |

## Lab & evals

10 `ops-*` lab scenarios (drift, selector, rollout, denial, expiry,
hash mismatch, staleness, lock conflict, partial failure, break-glass)
replay the pipeline with scripted transports — `lab run-all` covers
them; `evals/cases/ops-*` assert the governed verdicts.
