# EXECUTION — governed typed-action runs (Cycle 4 + 4.1)

Execution is the narrowest possible surface: a hash-pinned envelope
of typed actions, run through injected host transports, under locks,
preconditions and an append-only ledger. `dry_run=True` is the
default everywhere.

## The envelope — `ops/envelope.py`

`ExecutionEnvelope` binds: execution_id, intent_id,
`change_plan_hash`, executor, typed `actions`, `scope`,
`preconditions`, `policy_decisions`, `approvals`, `risk`,
`expected_delta`, `verification`, `rollback`, `idempotency_key`,
`expires_at`. `freeze()` pins the hash post-approval — any later
content change fails `is_intact()`.

Envelopes **never mint themselves**: `mint_envelope` requires
non-denied policy decisions and (cycle 4.1) a declared ExpectedDelta
for mutating plans — `PF-OPS-NO-DELTA` otherwise.

## Preconditions — `ops/preconditions.py`

- fresh observation (max age, default 900s),
- `current_plan_hash` == approved hash,
- expected vs current resource state,
- owner drift, policy decision presence,
- maintenance window / freeze (break-glass override only).

Any failure → `PF-OPS-PRECONDITION-*` with the failed check named.

## Step loop — `engine.execute()`

1. `check_approval` against the *actual* envelope hash + merged step
   params (bounds enforced here, not at mint).
2. Preconditions incl. TOCTOU resource-state comparison.
3. Resource locks (`LockTable`) — conflict → `PF-OPS-LOCK-CONFLICT`.
4. FSM walk to `executing` — only legal edges; resume skips
   completed steps.
5. DAG waves; per mutating step:
   - **`RollbackMaterial` captured before the step** (pre_state),
   - typed action dispatched to the executor's transport (stubbed in
     dry-run; real argv only host-side),
   - execution_result captured + material persisted to the CAS
     store; `material_hash` rides the step receipt.
6. Idempotency: identical effect keys are skipped.
7. Step failure → `failed`, downstream steps skipped
   (`dep-failed:<sid>`), locks released.
8. Post-execution the rollback plan is **rebuilt from captured
   materials** — the honest executability statement.

## Executors — `ops/executors/`

`git`, `terraform`/`tofu` (saved-plan sha256 binding + drift
precheck), `argocd`, `kubernetes` (narrow verbs; annotate is
prefix-allowlisted including remove-only form), `observe`
(read-only). Forbidden action names (`shell.run`, `kubectl.exec`,
`eval`, `aws.call`, `execute_anything`) refuse
`PF-OPS-UNSTRUCTURED` at `validate_action`.

## What execution refuses

- mutation without a transport (`PF-OPS-NO-TRANSPORT`),
- `--execute` under `--offline` (`PF-OPS-OFFLINE`),
- unknown actions/params (`PF-OPS-UNKNOWN-ACTION`,
  `PF-OPS-ACTION-PARAMS`),
- approval gaps/expiry/scope/bounds/tamper (`PF-OPS-APPROVAL-*`),
- production mutation from the offline core — always host-side.
