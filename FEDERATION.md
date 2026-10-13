# FEDERATION — intelligence exchange without credentials

`platformforge/federation/` lets multiple Platform Forge nodes
share **bounded intelligence**. It is not distributed execution and
never moves credentials (adversarial E8/E9).

## Model

`NodeManifest` (schema `platformforge/node-manifest/v1`): `node_id`,
`capabilities`, `data_freshness`, `export_policy` — per-classification
rules with **fail-closed default** (`deny` for unmapped
classifications).

## Export contract

`export_summary(node, payload, classification)` →
`platformforge/federation-summary/v1`:

- `deny` — restricted/confidential by default, or any payload
  containing a secret (scanned recursively; `api_key`, `password`,
  `token`, … trigger deny at **every** classification)
- `aggregate` — counts/distributions only, entries stripped
- `redact` — summary with sensitive fields replaced
- `share` — explicitly allowed tier only

## federated_query

`federated_query(nodes, query_fn, question)` fans a fleet question
to node-local summaries. Every node answers from *its own* data —
authority and credentials stay local. The result carries
`coverage` (answered/total) and the note "intelligence federation —
no execution authority crossed the boundary".

## Refused by the delegation contract

`direct-execution` · `approval-minting` · `shell-command` ·
`generic-provider-call` · `full-fleet-dump` · `credential-transfer`

→ `PF-OPS-CROSSFORGE-REFUSED` with an `unlock` instruction.

Allowed kinds are bounded reads only: `fleet-summary-request`,
`analytics-report-request`, `optimization-list-request`.

## Feature flag

`features.federation` defaults **off** (config v3) — the boundary is
opt-in, per repo.
