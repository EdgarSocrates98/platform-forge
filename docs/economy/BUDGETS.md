# BudgetEnvelope

Canonical contract: `platformforge/economy/budget.py` —
`platformforge/budget-envelope/v1`.

## Dimensions

`context_bytes`, `input_tokens`, `output_tokens`, `model_calls`,
`tool_calls`, `provider_calls`, `agents`, `fanout`, `parallelism`,
`wall_time`, `money`. Unknown dims are refused at construction.

## Limits

Each dimension carries `Limit(soft=, hard=)`:

- **soft** — a target; crossing emits `soft_exceeded` with the
  envelope's `soft_policy` (`warn`|`escalate`).
- **hard** — a wall; crossing emits `hard_exceeded` with the
  `overrun_action` (`reduce scope|reuse cache|switch deterministic|
  request escalation|return partial|refuse`). A hard limit is never
  crossed silently — exhaustion surfaces `PF-ECONOMY-BUDGET-EXHAUSTED`.

## Phase and role budgets

`phase_budgets` narrows limits per phase (`PHASES` + SDD phases);
`role_budgets` narrows per agent role (specialist, reviewer, critic,
referee, verifier). Effective limit = min of applicable candidates —
narrowing only ever tightens.

## Protected

`PROTECTED_ITEMS`: critical evidence, unresolved markers, security
findings, policy failures, rollback information, acceptance criteria.
`PROTECTED_PHASES`: VERIFY, SECURITY, CONTRACT — can never be removed
from a plan for cost reasons.

## Example

```python
env = BudgetEnvelope(limits={
    "context_bytes": Limit(soft=40_000, hard=200_000),
    "provider_calls": Limit(hard=0),       # offline posture
    "agents": Limit(hard=3)})
env.check("provider_calls", 1)  # Verdict(decision="hard_exceeded")
```
