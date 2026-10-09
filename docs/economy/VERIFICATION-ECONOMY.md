# Verification Economy

`platformforge/economy/verifyplan.py`. ADR-0060.

## Tiers

`V0-static < V1-contract < V2-unit < V3-integration < V4-runtime <
V5-production-evidence`

## Floors

- risk floors: `low→V0, medium→V1, high→V3, critical→V4`
- `impacted_nodes > 100` raises the floor to V2 (graph-aware)
- `change_scope` platform/org raises to V3
- `runtime_change` raises to V4
- `touches_security` / `security_sensitive` always adds the
  `security-verification` check — under any budget
- `budget_pressure` is *recorded* in reasons — it never lowers the floor

## Ledger

Each plan records `selected`, `skipped`, and per-check `reasons` —
selective verification is impact-scoped, auditable, and reversible;
it is never "skip tests to save time".
