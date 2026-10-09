# ADR-0059 — Declared provider pricing

Status: accepted · economy cycle (FE-002)

## Context

Provider cost math existed nowhere — dollar claims would have had to guess.

## Decision

ProviderPricing rows (provider, model, effective_at, currency, rates, source) are declared data, never hardcoded; cost() picks the newest effective rate and returns PF-ECONOMY-PRICING-MISSING when absent. Tool money is optional and only reported when reliable.

## Consequences

No dollar savings claim can exist without a declared rate + measured usage.
