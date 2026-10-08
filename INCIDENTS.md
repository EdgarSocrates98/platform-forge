# INCIDENTS — incident intelligence V3

`live/incident.py` + `platformforge live incident`.

`observe incident` (v2) correlates *declared* signals. V3 adds the live
side: a canonical timeline across change events + telemetry, and
deterministic candidate ranking with explicit factor weights — so a
postmortem states *why* each candidate was ranked, never vibes.

## Inputs

`--incident <json>` — `{timestamp, resources[]}` (+ optional `summary`).
`--changes <json>` — candidate change events (deploys, config changes,
drift events, apply records).
`--events <json>` — extra timeline events (alerts, telemetry markers).
`--window <s>` — correlation window (default 3600).

## Timeline

`normalize_event` lifts arbitrary shapes into canonical
`{timestamp, kind, actor, resources[], summary}` while preserving the
raw payload for scoring extras (e.g. `blast_radius`,
`runtime_correlated`). The timeline merges incident + changes + events,
sorted, each entry carrying evidence refs.

## Candidate scoring (factorized, deterministic)

score = 0.30·temporal_proximity + 0.15·graph_distance + 0.15·blast_radius
      + 0.10·scope_overlap + 0.15·runtime_correlation + 0.15·evidence

Every factor is named in the candidate record — scores are auditable,
reproducible, and tunable without hidden state.

| Status | Rule |
|---|---|
| `confirmed` | score ≥ 0.80 **and** causal evidence present (`evidence.causal`) |
| `supported` | score ≥ 0.65 |
| `candidate` | score ≥ 0.35 |
| `contradicted` | evidence contradicts the candidate |
| `unknown` | no factors above noise floor |

**Correlation is not causation**: nothing reaches `confirmed` on
proximity alone. Unresolved root cause stays `unresolved` — the
postmortem says so.

## Output

`postmortem_v3` — timeline, ranked candidates (status + per-factor
breakdown), `suspected_root_cause` (only when `confirmed`), blast radius
from graph edges, unresolved items. Strict mode exits 2 on unresolved.

Incident flows are read-only analysis: no notifications, no mutations.
