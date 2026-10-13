# Cycle 4 — Research Ledger

Per §177: `source, retrieved_at, version, capability, claims`. Sources
official or canonical (docs.argoproj.io, developer.hashicorp.com,
opentofu.org, kubernetes.io, sagas paper / microservices.io, OPA docs,
sigstore.dev). Retrieved during CYCLE-4 discover phase (Phase A, two
parallel research passes); condensed below into the claims that shaped
the design.

## ArgoCD / GitOps execution semantics

| Capability | Claims | Source | Design consequence |
|---|---|---|---|
| app sync | `argocd app sync` is declarative apply against the tracked Git revision; `--revision` pins the commit | docs.argoproj.io sync | `argocd.sync` action carries `revision` param — executor verifies it matches the envelope's plan hash lineage |
| sync options | `--prune`, `--dry-run`, `--resource` scoped sync; `--timeout`; `SyncStrategy` hook/apply | argocd user-guide | dry-run maps to `argocd app diff`/server-side dry-run; scoped `--resource` limits blast radius |
| rollback | `argocd app rollback` deprecated → rollback = sync to previous Git sha (GitOps-first) | argocd rollback deprecation | `argocd.rollback` action reverts via git sha, never `kubectl` mutation |
| health | app `.status.health.status` + sync status polled; Degraded ≠ Failed | argocd health docs | verification consumes health as *evidence*, not exit code |
| diff precheck | `argocd app diff --refresh` exposes live↔git drift before sync | argocd diff | drift precheck is a precondition input, refusal on mismatch with declared delta |

## Terraform / OpenTofu execution

| Capability | Claims | Source | Design consequence |
|---|---|---|---|
| saved plan | `terraform plan -out=FILE` produces a saved plan; `apply FILE` applies **exactly** that plan | developer.hashicorp.com plan/apply | `terraform.apply` binds `plan_sha256` — the envelope refuses apply of a different plan (`PF-OPS-PLAN-MISMATCH`) |
| plan as data | `terraform show -json FILE` → machine-readable `resource_changes[]` (actions create/update/delete/no-op) | tf show -json docs | `summarize_plan` produces the deterministic plan summary receipt |
| drift | `plan -refresh-only` / refresh on plan surfaces drift; `-detailed-exitcode` ⇒ 0 none, 1 err, 2 changes | tf plan docs | drift precheck runs before apply; exit code classifies, never parses text |
| lock | state locking default; `-lock-timeout` | tf state locking | executor surfaces lock errors verbatim → `PF-OPS-LOCK-CONFLICT` upstream |
| OpenTofu | 1:1 CLI parity for plan/apply/show | opentofu.org docs | `TofuExecutor` shares argv builders, different binary |

## Kubernetes mutation safety

| Capability | Claims | Source | Design consequence |
|---|---|---|---|
| scale | `kubectl scale` mutates the *desired* replicas on the API object | k8s scale docs | `kubernetes.scale` requires `current_replicas` precondition to catch drifted bases |
| rollout restart | patch-like restart via pod template annotation `kubectl.kubernetes.io/restartedAt` | k8s rollout docs | restart action carries the annotation evidence; rollback = not applicable → compensating scale/prev-revision |
| optimistic concurrency | `resourceVersion` precondition on update rejects stale writes | k8s api-concepts RV | annotate/update actions accept `resourceVersion` param |
| exec | `kubectl exec` runs arbitrary commands — excluded from vocabulary | k8s exec docs | `kubectl.exec` ∈ FORBIDDEN_ACTIONS → `PF-OPS-UNSTRUCTURED` |

## Approvals, policy, sagas

| Capability | Claims | Source | Design consequence |
|---|---|---|---|
| Four-eyes | change advisory / RFC approval semantics: approver ≠ requester, scope-bound, time-boxed | ITIL change enablement; CAB practice | `Approval` binds subject hash + scope + TTL + actor kind; `actor_kind=agent` never satisfies human approval |
| Policy-as-code | OPA decision = allow/deny over structured input; decoupled from enforcement | openpolicyagent.org | `adapter_eval` maps external verdicts; **fail-closed**: unreachable adapter → `unresolved`, never allow |
| Saga | compensating transactions roll back completed steps in reverse; not all steps are compensatable | microservices.io saga pattern | `derive_rollback` marks irreversible steps; `compensate_for` walks saga steps; prod never auto-rolls |
| Signed approvals | Sigstore/keyless sign-then-verify binds identity+payload | sigstore.dev | `Approval.signature` optional but verified when present; payload = canonical hash |
| Capability tokens | delegation grants must be scoped, non-amplifying | capability-security lit | `validate_delegate_request`: cross-Forge requests never carry execution authority |

## Honest boundaries

- No provider SDK in core — transports are argv (kubectl/argocd/
  terraform/git) or injected stubs; `host_transport()` is the only
  `subprocess.run` site and never sees a shell string.
- A5 experiments are lab-only by config (`auto_execute` gate +
  environment), matching the spec's "lab/non-production narrow
  reversible experiments".
- Research covers the verbs in the typed catalog; provider surfaces
  beyond those verbs are out of scope by design.
