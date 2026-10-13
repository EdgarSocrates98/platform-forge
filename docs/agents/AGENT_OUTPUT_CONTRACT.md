# Agent Output Contract

Specialists emit structured findings — never prose. Implemented in
`platformforge/agents/specialists.py`.

## Finding

```yaml
claim: <what is asserted>
status: supported | contradicted | absent | unresolved | unsupported
evidence: [fact_id, ...]
coverage: observed | partial | absent
freshness: fresh | stale | unknown
confidence: high | medium | low
limitations: [ ... ]
next_action: <verb or handoff>
```

## Rules

- A finding claiming `supported`/`contradicted` with no evidence is
  demoted to `unsupported` — mechanically, at validation.
- `absent` means "checked, not found"; `unresolved` means "could not
  check". They are never collapsed.
- `confidence` is derived from evidence tier + coverage, not asserted.
- Findings cite `fact_id`s, not file paths; stale evidence downgrades
  freshness, it does not disappear.

## Reviewer output

Reviewers emit checklists (`agents/reviewers.py`): each check is
`pass | fail | n/a` with a cited rule or evidence. A reviewer verdict
is `approve | request-changes | refuse` with mandatory checks listed.

## Verifier output

`verify_run` returns `verified | refused | unresolved` plus the
independence check result and per-gate receipts. A refused
verification blocks `done` — the run ends `refused`, not `partial`.
