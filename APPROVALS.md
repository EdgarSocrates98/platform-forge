# APPROVALS — hash-bound human gates (Cycle 4 + 4.1)

An approval binds a **human decision to an exact artifact hash**.
It is evidence, not authority-by-convention: `check_approval`
re-validates everything at execution time (TOCTOU defense).

## Model — `ops/approval.py`

`Approval` fields: `approval_id`, `subject_hash` (the envelope/plan
hash being approved), `scope` (resources), `actor`, `role`, `type`,
`decision`, `actor_kind`, `parameter_bounds`, `expires_at`,
`integrity_seal`.

Approval types: `automatic-policy`, `single-human`,
`resource-owner`, `platform-owner`, `security-review`, `dual-human`.

## Integrity seal (Cycle 4.1 §G / §145)

`integrity_seal` is a **content hash over the approval payload** —
tamper evidence, computed at mint time and re-verified at check time:

- **It proves** the approval's fields were not modified after sealing.
- **It does NOT prove** who approved — it is *not* a cryptographic
  signature and carries no signer-authentication claim. Naming and
  docs state this explicitly (`seal_semantics` in serialized form).
- `signature` remains only as a **deprecated serialization alias**
  for compatibility with older receipts.
- A modified sealed approval → `PF-OPS-APPROVAL-TAMPERED`.

## What check_approval enforces (§56–61)

- **Hash binding** — `subject_hash` must equal the current envelope
  hash; a changed plan → `PF-OPS-APPROVAL-STALE-PLAN`.
- **Actor kind** — only `human` satisfies human approval by default
  (`allow_actor_kinds`); an agent-minted approval cannot impersonate
  a human.
- **Required type** — `require-*` policy decisions and R5/prod R4+
  risk demand elevated types (`dual-human`, `security-review`, …).
- **TTL** — expired approvals → `PF-OPS-APPROVAL-EXPIRED`.
- **Scope** — approval scope must cover every target resource
  (`PF-OPS-APPROVAL-SCOPE`).
- **Parameter bounds** — approving `replicas 3→5` does not authorize
  `3→50` (`PF-OPS-APPROVAL-BOUNDS`); bounds are checked against the
  *actual* step params.
- **Seal integrity** — `PF-OPS-APPROVAL-TAMPERED`.

## Break glass

`BreakGlass` bypasses approval under a ticket + invocation reason +
scope + TTL — always audited, never silent. It produces its own
ledger events and does not weaken rollback/verification requirements.

## Minting approvals

`ops approve --subject-hash <envelope-hash> --actor <human>
--approval-type <type> [--bounds json] [--scope csv]
[--expires-at iso]` emits a sealed approval artifact. The MCP surface
`platformforge_ops` refuses approval minting entirely
(`PF-OPS-MCP-NO-APPROVAL`) — minting is human + host-side only.
