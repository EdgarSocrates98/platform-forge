# ADR-0012 — Collectors are a transport-pluggable adapter layer

Status: accepted · cycle 3

## Context

The core forbids provider SDKs and network. Live collection requires
both. The spec allows host-native mechanisms (kubeconfig, AWS CLI
profiles, standard SDK chain) and mandates fixture replay for tests.

## Decision

- `platformforge/collectors/` is the adapter layer: the only place
  network-capable code lives, behind `probe()/capabilities()/snapshot()/
  watch()/resume()`.
- Transports are substitutable: `FixtureTransport` (replay recorded
  responses — default for tests), `KubectlTransport` / `AWSCLITransport`
  (host CLI subprocesses using the user's own credential chain),
  `Boto3Transport` (optional `aws` extra, import-guarded).
- `--offline` or missing transport/credentials → `PF-LIVE-OFFLINE` /
  `PF-LIVE-CREDS` refusals, never silent fallback.
- All transports converge on identical envelope output.

## Consequences

- Core determinism preserved; every code path is fixture-testable.
- Credentials never enter the platform — the host CLIs/SDKs own them.
- Subprocess CLI transport avoids a hard boto3 dependency.
