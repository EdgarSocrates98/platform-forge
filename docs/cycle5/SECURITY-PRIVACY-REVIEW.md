# Cycle 5 — Security & Privacy Review

## Secret boundaries

- `federation/_contains_secret` scans payloads recursively
  (key names + values, depth-capped); `export_summary` denies
  secret-shaped payloads at **every** classification — including
  `public` (probe `fed-secret-denied`, adversarial E8).
- `AnalyticsStore.put_event` refuses payloads with credential-shaped
  keys (`PF-ANALYTICS-SECRET`).
- Redaction stays a boundary pipeline — `_redact` delegates to
  `live.store.redact_for_output`, the same redactor the rest of
  the platform uses.

## No-execution invariants

- `OptimizationEngine` has no `execute`/`envelope`/`mint` — the
  adversarial test inspects public methods, not docstrings (E7).
- Remote/federated nodes cannot mint approvals — the delegation
  contract refuses `approval-minting` and `direct-execution`
  (E9), and `NodeManifest.authority` is pinned `"local"`.
- Lab prod chaos still requires `--allow-prod`; unsupported
  profiles need `--allow-profile`.

## Privacy

- DX analytics (`analytics/dx.py`) measure **platform friction at
  team level**. `FORBIDDEN_METRICS` keys
  (`per_person`, `individual`, `developer_score`,
  `productivity_score`, `person_id`) are dropped from input;
  `guard_no_person_metrics` audits the emitted output (E10).
- Config pins are non-overridable: `privacy.dx_metrics` must stay
  `team-level-only`, `person_identifiers` `forbidden`
  (`PF-OPS-CONFIG-PRIVACY`).
- `forget_subject` deletes a subject's rows across
  events/snapshots/patterns and returns a receipt — right-to-forget
  is executable, not a paragraph (privacy gate).

## Evidence integrity

- `FleetSnapshot.to_dict()` hash-binds observations + fact refs.
- Optimization recommendations carry `evidence: [...]` — a rec
  without evidence cannot promote (E12: model-generated
  optimization cannot masquerade as measured fact — engine recs
  derive only from measured signals, never LLM text).

## Known limits (declared)

- `_contains_secret` is name+shape based — a well-formed payload
  with secrets under innocuous keys can pass `share`. Mitigation:
  classifications default deny; `share` is explicit opt-in.
- Federation transport security (mutual TLS, node auth) is
  host-side — the core only defines the boundary contract.
