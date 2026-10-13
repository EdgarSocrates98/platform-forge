# MCP — the Model Context Protocol surface

`platformforge-mcp` exposes the same deterministic core as the CLI.
Optional install:

```bash
pip install "platformforge[mcp]"
platformforge mcp serve            # stdio server
platformforge mcp tools            # list the capability surface
platformforge mcp call <tool> '<json args>'   # invoke one tool
```

## Contract

Every MCP tool is a projection of a `Capability` in
`platformforge/mcp/registry.py` — the same registry the CLI reads.
Parity between registry ↔ CLI ↔ MCP ↔ docs is tested
(`tests/test_mcp.py`, `tests/test_wave_l.py`), not assumed.

Each capability declares: `id`, `version`, `domain`, `input_schema`,
`output_schema`, `risk` (`read-only|propose|mutating`), `offline`,
`mutable`, `evidence_required`, `cost_class`, `agent_requirements`,
`detail_levels`.

## Boundaries (the safety contract)

- **Bounded output.** Every tool has a `detail_level` budget. Oversized
  results are stored in the content-addressed artifact store and
  returned as `artifact://sha256/<hash>` — never truncated mid-record.
- **Redaction.** `redact_obj` runs on every tool response before
  serialization (ADR-0005). Secrets do not cross this boundary even if
  a tool forgot to redact internally.
- **Read-only.** MCP is an observation surface. `approve`/`apply`-shaped
  calls refuse with a named code + unlock.
- **Refusals.** Insufficient evidence returns
  `{refusal: <PF-* code>, unlock: <action>}` — never empty output.

## Tool inventory

27 capabilities — generated from the registry:

```bash
platformforge capability list --json   # the real source
platformforge capability describe <id> # full v2 contract
platformforge capability check --domain k8s --version 1.29  # negotiate
platformforge forge manifest           # platformforge/capability-manifest/v2
```

Representative tools: `platformforge_analyze` (all domains incl.
`ownership`, `contradictions`, `cloud-*`, `kyverno`, `cosign`, `slsa`,
`hubble`), `platformforge_judge`, `platformforge_graph`,
`platformforge_plan` (remediation v2 DAG), `platformforge_explain`,
`platformforge_recommend`, `platformforge_security`,
`platformforge_reliability`, `platformforge_finops`, `platformforge_observe`,
`platformforge_change` (sandbox review), `platformforge_evals`,
`platformforge_context`, `platformforge_capability` (negotiation),
`platformforge_doctor`, `platformforge_live` (cycle3 observation surface),
`platformforge_ops` (cycle4 governed operations — PREPARE only: plan/
simulate/risk/gates/policy/envelope, status/history/graph/analytics;
`approve` and any execution refuse `PF-OPS-MCP-*` — delegation never
carries mutation or signing authority).

Cycle 5 surfaces are exposed read-only via five tools —
`platformforge_fleet` (all fleet verbs incl. `report`),
`platformforge_analytics`, `platformforge_optimize` (`plan` emits the
ChangeIntent document but can never write it — `out` is forced off on
this surface), `platformforge_ai`, `platformforge_federation`

Economy control plane tools (read-only — no `routing.activate`):
`platformforge_economy_explain` (per-run checkpoint + ledger),
`platformforge_context_inspect`, `platformforge_context_expand` (lazy
capsule sections), `platformforge_routing_explain` (decision receipt).
(classified summaries only; secrets always denied; no authority
crosses). Boundaries unchanged: all `read` risk, `mutable: false`,
bounded output, same `cmd_*` functions the CLI calls — there is no
MCP-only code path.

## Host integration

`platformforge mcp integrate --host <host>` writes the host's parity
config (Claude Desktop / compatible MCP hosts). `detach` removes it.
Host mutation is confined to the parity files — the core stays untouched.
