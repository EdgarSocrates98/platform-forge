# Checkpoint & Resume

`platformforge/economy/checkpoint.py`. ADR-0057.

## What persists

`EconomyCheckpoint`: run_id, spent_budget, remaining_budget,
context_refs, cache_refs, agent_state, routing_profile, risk_profile,
tool_spend, provider_spend, deps (artifact_hash / knowledge_hash /
policy_version), created_at.

## Resume semantics

`CheckpointStore.resume(run_id, current_deps, requested_profile)`:

- **Spend carries over** — tokens, agents, tool calls and provider
  calls are never reset.
- **Deps revalidated** — any dep that drifted is reported in
  `stale_deps` and `needs_revalidation=True`; stale sections must be
  re-verified, not reused.
- **No downgrade** — resuming a `deep` run as `economy` refuses with
  `PF-CHECKPOINT-DOWNGRADE`; upgrade is allowed.
- **Missing checkpoint** — `PF-CHECKPOINT-MISSING` with `unlock: start
  a fresh run — spend unknown`.

## CLI

```bash
platformforge economy checkpoint --run-id r1 \
  --spent '{"tokens":500}' --profile deep --deps '{"policy_version":"p1"}'
platformforge economy resume --run-id r1 --profile deep
platformforge economy explain --run-id r1   # checkpoint + ledger view
```
