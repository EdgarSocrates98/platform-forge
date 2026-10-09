# Agentic Economy Report

Evidence for agentic cost governance (spec §117–160, Phase L/M/N/O).

## Fanout audit

`AgentUniqueness` classifies every invoked agent's contribution ids:
unique / duplicated / refuted / discarded. Zero-unique agents emit
`unused_agent` waste findings — a routing-review recommendation, never
an auto-fix, never a people leaderboard.

## Debate economy

- Positions must cite evidence; participants and rounds are bounded;
  over-bound input refuses rather than truncating.
- Rounds group deterministically; a round adding no new evidence ids
  stops the debate (`stopped_early`, `stagnant_round`, `stop_reason`).
- `build_referee_packet` emits positions + deltas + shared evidence +
  contradictions + budget — never a transcript.
- Referee adjudication stays separate from verification:
  `verifier_required` is always true in the receipt.

## Routing control plane

- Five profiles (economy/balanced/deep/strict/offline); risk floors
  raise the effective profile and can never lower it.
- Every decision emits a receipt: inputs hash + policy_version +
  decision + reason + estimated budget.
- Champion/challenger: `promote_verdict` requires quality+safety+
  economy gates AND human approval; verdict `awaiting_human` is the
  best a shadow candidate gets alone (eval E10).

## Waste detector

10 waste types over `.platformforge/ledger/*.jsonl` — duplicate
context/tool call, repeated graph build, unused agent, overrouting,
repeated provider call, unused expansion, cache bypass, oversized
context, unnecessary verification. Advisory findings with evidence,
confidence and recommended fix.

## Tool output economy

`rtk.tool_economy_receipt` reports raw/compact/expanded bytes; compact
is the default model surface, raw stays an artifact, expansion is on
demand. Caveman compression keeps protecting IDs/codes/versions/paths/
warnings/security markers and redacts first.
