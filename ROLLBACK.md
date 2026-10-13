# ROLLBACK — material-bound reversal (Cycle 4.1)

Rollback in Platform Forge is a *governed, evidence-driven* process —
never a blind inverse of the forward action. This document explains
the five distinct concepts the spec (§162) requires us to keep
separate:

```
rollback action        the typed action executed to reverse a step
rollback material      immutable evidence captured around the forward step
rollback plan          strategy + status derived FROM material
rollback execution     the governed run of the plan's typed actions
rollback verification  restored|partially-restored|regressed|unknown
```

**action ≠ material ≠ plan ≠ execution ≠ verification.** Conflating
any two is exactly how "rollback" becomes a second, untested mutation.

## The five concepts

### 1. RollbackMaterial — `ops/material.py`

Captured for **every mutating step** during `engine.execute()`:

- `pre_state` — snapshot taken **before** the step runs (params-declared
  values merged with caller-supplied `preconditions.pre_state`;
  observed wins over declared, and `provenance` records which tier
  was used).
- `execution_result` — the step's outputs captured **after** it runs
  (resulting commits, PR numbers, resource versions).
- `source_of_truth` — the SoT context for the step, so a later plan
  can choose source-aware reversal paths honestly.
- `limitations` — missing required pre-state keys; any limitation
  blocks an *executable* rollback status.
- `hash` — sha256 over the canonical payload. Materials are
  **immutable and content-addressed** (`.platformforge/materials/
  <hash>.json`, write-once). `payload()` deep-copies mutable fields —
  mutating a serialized dict cannot corrupt the live object.

### 2. Rollback action

A typed action from the same vocabulary as forward actions (e.g.
`kubernetes.scale`, `git.revert_commit`, `argocd.rollback`,
`kubernetes.rollout_undo`). Rollback actions are **built**, not
inverted: `ops/rollback_builders.py` maps each forward action to a
builder that reads the material and emits concrete params — e.g.
`kubernetes.scale` restores `pre_state.replicas`; `kubernetes.annotate`
restores captured annotations and `remove_annotations` only the keys
the forward step *added*; `git.commit` reverts the **resulting**
commit from `execution_result`, not `pre_change_commit`.

A saved Terraform/OpenTofu **forward plan is never a reverse plan**
(§15–19): `terraform_plan_reuse_check` refuses `PF-OPS-PLAN-REUSE`,
and the builder emits a *replan descriptor* (`source_ref`,
`forward_plan_hash`) — reversal is a new governed operation
(source-revert → new plan → new approval).

### 3. RollbackPlan v2 — `ops/rollback.py`

Schema `platformforge/rollback-plan/v2`:

| Field | Meaning |
|---|---|
| `strategy` | worst-of step strategies: `direct-inverse`, `source-revert`, `previous-revision`, `compensating-operation`, `replan-required`, `manual-only`, `impossible`, `unknown` |
| `status` | `executable` \| `requires-replan` \| `manual-only` \| `impossible` \| `unresolved` |
| `actions` | typed rollback actions (validated through `validate_action`) |
| `material_hashes` | the material bindings this plan stands on |
| `replans` | replan descriptors for replan-required steps |
| `limitations` | honest gaps preventing executable status |
| `automatic` | may run without human trigger — **lab/non-prod only**, and only when `status == "executable"` |

**"rollback ready" is only valid when `status == "executable"`.**
Every other status is an honest refusal reason, never a hidden guess.

### 4. Rollback execution — `engine.execute_rollback()`

- Typed **trigger** (`{type, verification_id, observed_delta,
  slo_evidence, at}`) — never a bare reason string.
- Only `status == "executable"` runs actions; everything else refuses
  `PF-OPS-ROLLBACK-NOT-EXECUTABLE` with the limitations and replan
  descriptors attached.
- Same resource **locks** as the forward op (§157–158), same
  **idempotency** (a `rolled-back` op returns the prior receipt).
- **Rollback preconditions** (§159): if the resource no longer matches
  the failed-forward state (`current_matches_forward=False` in
  material pre-state), the run refuses `PF-OPS-ROLLBACK-PRECONDITION`
  → human review; a blind revert of someone else's change is never
  attempted.
- **Failure** (§149–153): a failed rollback step transitions the op to
  `failed` with `stage=rollback` + `escalation=human-required` —
  never `rolled-back`, never an automatic second rollback (§148/150).

### 5. Rollback verification — `engine.verify_rollback()`

Command success (`rc=0`) is **not** restoration. Post-rollback state
is compared against captured `pre_state` per dimension:

- `restored` — every captured dimension matches.
- `partially-restored` — some restored, some different/unobserved.
- `regressed` — observed values differ from pre-state (a *new*
  regression is surfaced, not hidden by the rollback receipt).
- `unknown` — no post-rollback observation → never
  restored-by-assumption.
- `not-applicable` — no materials captured.

Concurrency tokens (`resource_version`, `uid`, `generation`) are
precondition evidence, not restorable dimensions — they are excluded
from the comparison.

The §40 receipt carries: operation_id, stage, result, trigger,
strategy, material_hashes, rollback_plan_ref (envelope hash),
actions, rollback_verification, and per-dimension comparisons.

## Operational graph

`project_operation()` emits a `rollback` node + `rolled_back_by` edge
citing trigger, strategy, material_hashes and the ledger receipt ids.
`validate_projection()` reports orphan nodes and evidence-free edges —
the graph is auditable, not decorative.

## Lab & evals

Lab scenarios (all green, scripted transports — nothing touches a
host): `ops-rollback-scale`, `ops-rollback-annotate`,
`ops-rollback-gitops`, `ops-rollback-terraform`,
`ops-rollback-impossible` (+ the original `ops-bad-rollout`).

Eval cases: `rollback-k8s-scale`, `rollback-k8s-annotation-restore`,
`rollback-git-commit`, `rollback-argocd-revision`,
`rollback-terraform-replan`, `rollback-unknown`,
`rollback-impossible`, `rollback-material-tamper`,
`rollback-blind-inverse`, `expected-delta-refusal`, `sot-conflict`,
`approval-integrity-seal`.

Adversarial evidence lives in `tests/test_ops_adversarial41.py`
(waves R1–R6: wrong-params reuse, plan reuse, missing history id,
annotation destruction, forgery, staleness, wrong resource,
delta-free minting, vacuous convergence, SoT auto-exec, seal
semantics, success≠restored, regression detection, failed rollback).

## What rollback will never do

- Invent an action when material/status is insufficient.
- Reuse forward params as an inverse.
- Treat a Terraform forward plan as its own rollback.
- Auto-execute outside lab/non-prod, or on a non-executable status.
- Claim `restored` from command exit codes.
- Run a second automatic rollback after a rollback failure.
- Execute on a resource that drifted since the forward failure.
