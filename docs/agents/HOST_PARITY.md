# Host Parity

The canonical roster (`platformforge/agents/roster.py`) is the single
source of truth. Host mirrors are **generated, never hand-edited**.

## Targets

| Directory | Format | Count (41-agent roster) |
|---|---|---|
| `agents/` | markdown | 41 |
| `.agents/agents/` | markdown | 41 |
| `.claude/agents/` | markdown | 41 |
| `.codex/agents/` | toml | 41 |
| `.devin/agents/` | markdown | 41 |

205 files total; regenerate with `platformforge agents sync`.

## Commands

```bash
platformforge agents list      # roster dump
platformforge agents lint      # contract lint
platformforge agents sync      # regenerate all mirrors
platformforge agents check     # drift gate: missing/stale/stray
platformforge agents playbook  # zero-subagent fallback plan
platformforge agents referee   # bounded debate
```

`agents-mirrors` gate fails on any missing, stale, or stray `.md`/`.toml`
under mirror roots.

## Zero-subagent fallback

Hosts without subagents use `platformforge agents playbook <task>`: a
sequenced human-run plan carrying the **same** evidence requirements,
reviewers, and verifier as the agentic route — capability parity, not
capability loss (eval `host-no-subagents` enforces this).

## Parity rules

- Mirror content derives only from `AgentSpec.to_dict()` — no extra
  permissions can appear on a host that the contract doesn't grant.
- A permission escalation through a mirror is a contract violation
  (adversarial case A-series).
- Mirrors embed role, access, write scope, model tier, budgets,
  domains, entry conditions, exclusions, delegation boundaries,
  reviewers, verifier, escalation, `done_when`, and `never`.
