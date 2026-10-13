# Multilayer Cache

`platformforge/economy/cache.py` — `CacheStore`, `CacheDecision`.
ADR-0054.

## Layers and bound dependencies

| Layer | Invalidated by |
|---|---|
| artifact | runtime_version |
| fact | artifact_hash, extractor_version, runtime_version |
| graph | artifact_hash, runtime_version, config_hash |
| finding | artifact_hash, rule_catalog_hash, knowledge_hash, policy_hash |
| context | artifact_hash, rule_catalog_hash, knowledge_hash |
| analysis | rule_catalog_hash, knowledge_hash, engine_version, policy_hash |
| decision | evidence_hash, policy_version, risk_profile |

A dependency a layer does not bind cannot invalidate it — that is
**selective invalidation**: a rule-catalog change keeps facts cached
while every finding/analysis/decision misses. The §292 north star —
facts survive, judgments recompute.

## Decisions and receipts

Every `get` returns `CacheDecision(state, layer, key, reason,
changed_deps, entry_age_s)` — `hit|miss|stale|invalid|partial-reuse`.
`reuse_plan` reports which layers hit vs recompute for a dep set.

## Rules

- Keys are content+dependency hashed; payloads flagged sensitive are
  refused at `put` (credentials, secret values, approval tokens are
  never cached).
- TTL per entry; `gc()` removes expired entries.
- `invalidate_dep(key, new_value)` removes every entry bound to a
  changed dep — transitively.
- `stats()` exposes hits, misses, bytes reused, entries, invalidations,
  per-layer counts.
- CLI: `cache stats|inspect|invalidate|gc`.
