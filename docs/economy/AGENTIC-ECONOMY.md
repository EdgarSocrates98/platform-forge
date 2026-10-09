# Agentic Economy

`platformforge/agents/uniqueness.py` + `agents/debate.py` +
`economy/waste.py` + `rtk/compact.py`. ADR-0061.

## Fanout audit

`AgentUniqueness(run_id).audit([AgentContribution(agent,
contribution_ids, refuted, discarded)])` classifies each agent's
output ids: unique / duplicated / refuted / discarded. An agent with
zero unique contribution emits an `unused_agent` waste finding —
a *recommendation* for routing review, never an auto-fix, never a
leaderboard of people.

Bounds live in the envelope: `agents`, `parallelism`, `fanout`.

## Debate economy

`run_debate` bounds participants and rounds; positions must cite
evidence; rounds are grouped deterministically and a round that adds
no new evidence ids stops the debate (`stopped_early`,
`stagnant_round`, `stop_reason`). `build_referee_packet` emits the
compressed structured view — positions + deltas + shared evidence +
contradictions + budget — never a transcript. The referee adjudicates
disagreement; independent verification stays a separate step
(`verifier_required: True`).

## Waste detector

`EconomyWasteDetector(root).detect()` scans `.platformforge/ledger`
for: duplicate context, duplicate tool call, repeated graph build,
unused agent, overrouting, repeated provider call, unused expansion,
cache bypass, oversized context, unnecessary verification — each with
evidence, confidence and a recommended fix. Findings are advisory.

## Tool output economy

`rtk.tool_economy_receipt(cmd, res, raw_bytes, expanded_bytes)` reports
raw vs compact vs expanded bytes; raw output stays an artifact, compact
is the default model surface, expansion is on demand.
