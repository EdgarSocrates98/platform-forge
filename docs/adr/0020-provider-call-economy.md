# ADR-0020 — Provider calls are a budgeted, ledgered resource

Status: accepted · cycle 3

## Context

Live systems generate far more data than repos. Blindly calling every
API is slow, costly and throttled; silently sampling hides coverage
loss.

## Decision

- `ObservationBudget`: max_objects/events/bytes/api_calls/duration/
  clusters/accounts/regions — enforced inside collectors; outcomes are
  `complete|reduced_scope|sampled|refused`, always declared in coverage.
- `ProviderCallLedger` per collection: calls, pages, objects, bytes,
  retries, throttles, cache_hits, duration — feeds Economy V3.
- Metadata-first inventory (K8s PartialObjectMetadata; AWS broad
  inventory → targeted deep fetch) is the default fetch strategy;
  content fingerprints enable delta ingestion (unchanged resource →
  reuse facts).
- Monetary cost is reported only with trusted pricing input — never
  invented.

## Consequences

- TokenSave philosophy extends to provider calls: quality-per-call is
  measured on benches, not claimed.
- Budget exhaustion is a first-class refusal, not silent truncation.
