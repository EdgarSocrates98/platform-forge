# RUNTIME-TOPOLOGY — observed edges

`live/topology.py` + `platformforge live topology`. Runtime evidence
produces **observed-layer edges** on the graph — never inferred-declared.

## Sources

| Source | Input | Emits |
|---|---|---|
| OpenTelemetry spans | `--otel` OTLP JSON (list or `{"spans":[]}`) | `service --calls→ service` edges; semconv attrs (`service.name`, `peer.service`, `http`, `rpc`, `db.system`) mapped to vocab kinds |
| Cilium/Hubble flows | `--hubble` flows JSON | L4↔L7 `routes_to`/`calls` edges pod↔service↔external (`ext:*` service nodes) |
| EndpointSlices | `--slices` JSON | `service --runs_on/exposes→ pod` membership edges |

Only whitelisted attributes become edge/fact content — telemetry is a
noisy untrusted surface, so it is parsed to a controlled projection.

## Behavior classes

Each runtime edge is classified against the graph:

- `declared` — a backing edge exists (declared or planned layer).
- `observed` — observed only, plausibly runtime-born (e.g. `ext:*`).
- `observed-undeclared` — runtime behavior with no declared backing:
  flagged as `runtime-undeclared` drift by reconcile.

## Temporal semantics

Edges carry `temporal: {first_seen, last_seen, sample_count}` and a
`provenance` layer (`observed` here). `graph/temporal.py`:
`expire_stale_edges(g, now, max_age_s)` marks `temporal.expired=true` —
edges are **marked, never deleted**, so history is auditable;
`temporal_between(g, t0, t1)` returns edges active in a window for
incident timelines.

`--apply-to-graph` persists via `graph.apply_runtime_edges` (multi-layer
evidence merge — one edge keeps all contributing provenances).
