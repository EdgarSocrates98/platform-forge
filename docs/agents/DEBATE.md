# Debate

`platformforge/agents/debate.py` — bounded, evidence-cited
disagreement. Schema: `contracts/debate.schema.json`.

## Bounds

- Participants: 2 specialists + 1 critic + 1 referee (default; small,
  never a swarm).
- Rounds: 1–3, hard cap.
- Budget: charged to the run's `AgentRunEnvelope`.

## Rules

- Every position must cite evidence (`fact_id`s). A position without
  evidence is refused at intake — not downgraded, refused.
- The critic attacks evidence gaps and unsupported claims only.
- Referee output: `winner | tied | unresolved` + axes + receipt.

## Referee axes (10)

evidence quality · coverage · freshness · risk · feasibility ·
reversibility · blast radius · cost · precedent · residual uncertainty.
Each axis is scored per position from cited evidence; `tied` is an
honest outcome, not a failure.

## Independence

The referee resolves the *disagreement* — it does not verify the
*result*. Every debate route still ends at `platform-verifier`.
A referee that declares a winner also records which evidence was
decisive, so the verifier can re-check it independently.
