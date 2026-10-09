# ADR-0018 — Runtime edges prove communication; absence proves nothing

Status: accepted · cycle 3

## Context

Only traces/flows/network telemetry prove actual communication.
EndpointSlices prove routing membership, not traffic. Sampled traces and
finite flow buffers make "no edge" weak evidence.

## Decision

- Runtime edge evidence: tier T0, provenance observed,
  source_type=runtime; carries window {first_seen,last_seen,count}.
- EndpointSlice → `routes_to` (T1, routing membership); OTel CLIENT→
  SERVER pairing / Hubble FORWARDED flows / mesh counters → `calls`/`reads`/
  `writes` (T0, actual traffic). DROPPED = attempted-only; AUDIT =
  passed-in-audit-mode.
- Declared-vs-runtime behavior classes: declared-and-observed |
  observed-undeclared | declared-not-seen-in-window | unknown. The third
  is never a finding by itself.
- Edges expire by marking `not_recently_observed`; history preserved.

## Consequences

- "Who actually talks to whom" is answerable with evidence; "who
  doesn't" stays honest about sampling/coverage.
