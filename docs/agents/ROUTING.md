# Routing

Router V2: `platformforge/routing/router.py`, data in
`rules/catalog/routing.yaml`. Returns a full route decision — mode,
DAG, budgets, reviewers, verifier, reasons — or a bounded fallback.

## Signals

Task type · domains · complexity · risk · blast radius · security
sensitivity · production status · evidence availability/completeness ·
coverage · freshness · expected provider+token cost · mutability ·
fleet scope · incident status · conflict/comparison · destructive /
optimization flags.

## Modes

| Mode | When |
|---|---|
| `deterministic` | a verb answers it — zero agents |
| `single-specialist` | one domain owns it |
| `multi-specialist` | ≥2 domains, independent findings |
| `coordinated` | cross-domain, shared state needed |
| `debate` | conflicting positions/comparison, bounded |
| `critical-review` | production/security-sensitive change |

Non-deterministic routes always include `platform-verifier`.
Critical routes add operations-safety + security reviewers.

## DAG output

The route emits an instantiated DAG (from `rules/catalog/
orchestration.yaml` templates). `build_dag` resolves stage refs
against the live roster — unknown agents are reported as `missing`,
never silently dispatched.

## Validation

`validate_routing()` (gate `agents-routing`) fails if any name in
`routing.yaml`, loop templates, or coordinator `delegates_to` is absent
from the canonical roster — this closes the Cycle-5 drift where six
routed names didn't exist.

## Cost

Every decision includes a projected cost (fanout × context class)
with `measured: projected` honesty — real run rows come from the
run ledger.
