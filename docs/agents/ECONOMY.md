# Agent Economy

`agents/contextpack.py` · `economy/envelope.py` · `economy/engine.py` ·
`tokensave/ledger.py` · `agents/runledger.py`.

## Context discipline

```
Task → Graph scope → Evidence → ContextPack
```

Never the whole repository. A context pack carries: task summary,
relevant evidence, graph neighborhood (bounded hops), rules, knowledge
references, recent operations, open questions, and its budget class.

## Budget classes

`tiny` · `small` · `standard` · `deep` · `critical` — ceilings on
model calls, context bytes, tool calls, agents, fanout, duration.
Charge with `env.charge(...)` *before* spend; `env.check()` returns a
`partial` refusal when a class is exceeded — never silent success.

## Delta context

Follow-up agents receive `previous_context_hash + delta` whenever the
pack is rebuildable — context reuse is measured in the ledger as
`cache_reuse`.

## Agent run ledger

Per run: model calls, context bytes, output bytes, tools used, agents
spawned, fanout, duration, cache reuse. Records persist under
`.platformforge/runs/` and feed `platformforge agents bench` — which
reports `measured: projected` until real run rows exist (no
extrapolation from projections).

## Strategy comparison

`agents bench` compares deterministic / single-specialist /
multi-specialist / coordinated / debate over the fixed task set —
multi-agent is never assumed better; it must be proven.


## Economy control plane integration

Agent context now flows through `context/gateway.py` (capsules +
`context://` refs, measured sufficiency, essential-evidence refusal);
fanout is audited per run by `agents/uniqueness.py` (unique/duplicated/
refuted/discarded contribution; zero-contribution → `unused_agent`
recommendation); debates stop when a round adds no new evidence and the
referee consumes a structured `RefereePacket`, not a transcript.
Routing decisions emit receipts and promote only through human-approved
champion/challenger gates (`routing/decision.py`). Budget ceilings
above compose with the unified `BudgetEnvelope` — protected phases
(VERIFY/SECURITY/CONTRACT) are outside economy.
