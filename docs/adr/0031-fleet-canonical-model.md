# ADR-0031 — Fleet canonical model

Status: accepted · cycle 5

## Context

Fleets need one identity scheme across heterogeneous members (clusters, accounts, repos, services, teams) so analytics can join them without collisions.

## Decision

member_key(kind, canonical_id) is the sole identity; FleetSnapshot carries MemberObservation coverage per member — coverage is a first-class field of every fleet answer.

## Consequences

Consumers must keep coverage visible; partial data never completes silently.
