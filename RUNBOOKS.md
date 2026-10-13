# RUNBOOKS — parameterized governed procedures (Cycle 4 + 4.1)

Runbooks are **data, not scripts**: trigger, scope, diagnostics,
preconditions, typed steps, risk, approval, verification, rollback,
knowledge sources. `bind()` compiles one to `PlanStep`s that flow
through the same governed pipeline as everything else.

## Audit contract — `Runbook.audit()`

Refusals for malformed runbooks:

- `PF-OPS-RUNBOOK-NO-TRIGGER` / `NO-SOURCE` — every runbook names
  when it applies and cites knowledge sources;
- `PF-OPS-RUNBOOK-DUP-STEP` / `BAD-DEP` — step identity + DAG sanity;
- `PF-OPS-UNKNOWN-ACTION` — execute and rollback actions must come
  from the typed vocabulary;
- `PF-OPS-RUNBOOK-DIAG-NO-SOURCE` — diagnostics name evidence;
- `PF-OPS-RUNBOOK-BAD-REF` — `from:` params outside allowlisted roots.

## Safe parameter references (cycle 4.1 §123–127)

Rollback params must not hardcode an inverse of the forward params.
Declare a reference instead:

```yaml
rollback:
  strategy: direct-inverse
  actions:
    - action: kubernetes.scale
      for_step: scale
      params:
        replicas:
          from: pre_state.replicas     # captured material, not params
```

`bind_rollback(materials)` resolves `{from: root.path}` at
rollback-compile time:

- **allowlisted roots only** — `pre_state`, `params`, `result`;
- **no eval, no template engine** — pure dict path walking;
- missing path → `PF-OPS-RUNBOOK-REF-MISSING`;
- disallowed root → `PF-OPS-RUNBOOK-BAD-REF`.

## Builtins

- `replica-drift-restore` — GitOps-managed drift → `git.open_pr` +
  `argocd.sync`; rollback via argo history.
- `scale-out-under-pressure` — non-prod scale for load; rollback
  restores `pre_state.replicas` via safe ref.

## Golden paths reuse the same contracts

`PlatformRequest.to_change_intent()` emits a `ChangeIntent` — golden
path provisioning flows intent→plan→policy→approve→execute→verify
like any governed change. There is no parallel provisioning workflow
(§128–129).
