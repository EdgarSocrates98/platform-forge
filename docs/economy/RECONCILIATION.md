# Budget Reconciliation

`platformforge/economy/reconcile.py`. ADR-0058.

## Axes

`tokens`, `context`, `tools`, `agents`, `provider_calls`, `duration`,
`money`.

## Semantics

`reconcile(planned, observed)` compares per axis:

- `ok` — |error%| within tolerance (default 20%)
- `over` / `under` — calibration error reported as percent
- `unresolved` — either side unmeasured. **An unmeasured axis is never
  zero**; a plan with no observation is a gap, not a success.

`savings_claim` refuses dollar claims without observed usage and
declared pricing — no "we saved $X" from estimates.

## Example

```python
rec = reconcile(planned={"tokens": 1000}, observed={"tokens": 2400})
rec.axes["tokens"].state      # "over"
rec.axes["tokens"].error_pct  # 140.0
```

## CLI

`economy reconcile --planned '{"tokens":1000}' --observed '{"tokens":2400}'`
