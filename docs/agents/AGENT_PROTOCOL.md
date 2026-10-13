# Agent Protocol

Canonical contract for every agent in Platform Forge. Source of truth:
`platformforge/agents/contracts.py` + `platformforge/agents/roster.py`.
Schemas: `contracts/agent-spec.schema.json`, `contracts/task-spec.schema.json`,
`contracts/agent-handoff.schema.json`, `contracts/agent-run.schema.json`,
`contracts/debate.schema.json`.

## Primitives

| Contract | Module | Purpose |
|---|---|---|
| `AgentSpec` v2 | `agents/roster.py` | Who the agent is, what it may do, what it must never do |
| `PlatformTaskSpec` | `agents/taskspec.py` | A sealed unit of work with evidence requirements |
| `AgentHandoff` | `agents/contracts.py` | A typed handoff between agents with context pack ref |
| `AgentRunEnvelope` | `agents/contracts.py` | Per-run budget counters; charge before spend |
| `RunRecord` | `agents/runledger.py` | Persisted run: router decision, agents, evidence, verdict |
| `Debate` | `agents/debate.py` | Bounded, evidence-cited disagreement |

## Task lifecycle

```
intent → plan() → review() → sealed TaskSpec
       → route() → DAG of stages
       → dispatch per stage → findings
       → reviewers → verifier → RunRecord verdict
```

Task states: `draft → reviewed → sealed → routed → running →
verifying → done|refused|partial|unresolved`. A spec without evidence
requirements cannot be sealed. `planned ≠ observed` is preserved
end-to-end.

## Handoff rules

- Handoffs carry a context-pack hash, never raw repository dumps.
- Delegation graph is closed: `delegates_to` is explicit;
  `cannot_delegate_to` denies are checked at dispatch.
- Executors never delegate.
- A producer may not be its own verifier — enforced at seal and at
  `verify_run` time.

## Refusals

Every refusal carries a `PF-*` code plus an `unlock` instruction.
Budget exhaustion yields `partial`, never silent success.
