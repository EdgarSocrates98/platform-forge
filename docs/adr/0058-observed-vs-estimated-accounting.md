# ADR-0058 — Observed vs estimated accounting

Status: accepted · economy cycle (FE-002)

## Context

Byte counts were being summed with provider token counts — a number that cannot exist.

## Decision

token_basis is a closed vocab (observed|estimated|unknown). Observed rows must bind a transcript_ref; observed and estimated are reported in separate fields forever and never summed into a single token figure. Unknown usage is reported as unknown, not zero.

## Consequences

Any cost claim carries its basis; mixing bases is a contract violation caught at the ledger.
