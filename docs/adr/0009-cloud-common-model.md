# ADR-0009 — One cloud common model; providers are dump adapters

Status: accepted · cycle 2

## Context

AWS/Azure/GCP facts must feed the same graph and rules without three
parallel taxonomies.

## Decision

- `cloud/common.py` normalizes dumps into `cloud.*` facts with a shared
  vocabulary (account, region, vpc_vnet, subnet, cluster, database,
  bucket, function, queue, topic, iam_principal, role, policy).
- Provider analyzers (`cloud-aws|azure|gcp`) are shape-sniffing dump
  readers that emit T1 provider-observed facts from CLI JSON exports.
- No provider SDK in core; `collect` stays dump-only (read-only boundary).
- The same rules apply across providers via fact kinds and attrs.

## Consequences

Adding a provider means writing a shape-sniffer, not a domain. Azure/GCP
coverage is partial and declared as such in CAPABILITIES.md.
