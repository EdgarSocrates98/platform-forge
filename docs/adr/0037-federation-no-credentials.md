# ADR-0037 — Federation without credential sharing

Status: accepted · cycle 5

## Context

Sharing data across forges is useful; sharing authority or secrets is not.

## Decision

export_summary is classification-driven with deny-by-default, recursive secret scan, aggregate/redact/share actions; delegation contract refuses exec/mint/shell/provider/full-dump/credential-transfer; federated_query is node-local answering.

## Consequences

Intelligence crosses, authority never does; remote nodes cannot gain execution.
