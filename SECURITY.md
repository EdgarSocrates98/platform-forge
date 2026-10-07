# SECURITY — defensive platform analysis & the redaction boundary

Platform Forge analyzes security posture from artifacts — it never
exploits, escalates or exfiltrates.

## Analyzers

| Domain | Input | Produces |
|---|---|---|
| `secrets` | file tree | labeled findings — never secret values |
| `iam` | AWS IAM policy JSON | principal/action/resource graph, trust, SCP, permission boundary, OIDC, role chaining (§100) |
| `sbom` | SPDX/CycloneDX + offline vuln list | component facts, CVE/license joins |
| `supply` | repo CI/CD + deps | supply-chain posture |
| `kyverno` | policy dir + declared version | version-aware deprecation/validations |
| `cosign` | bundle/statement | claimed ≠ verified (shape, no crypto) |
| `slsa` | provenance doc | requirement/evidence/gap |
| `hubble` | Cilium flow dumps | T0/T1 observed flow facts |

## Identity paths (§101)

`graph identity-become|access|workloads|blast` — who can assume a role,
reach a workload, or the blast of a compromise. "No path found" is a
named result, never "no risk".

## Boundaries (§158–159)

- The core is read-only; `change approve|apply` refuse — execution is
  host-side behind an explicit gate.
- Non-static Lab profiles require `--allow-profile` + safety contract.
- `analyze secrets` emits labels + locations; values never cross facts,
  context packs, Caveman output or MCP responses (ADR-0005).
- `ownership.conflicted` / `state.contradiction` surface disagreement
  instead of picking a silent winner (§116, §137).

## Tests

`tests/test_wave_k.py` + `test_wave_l.py` cover: secret never in
ContextPack / MCP response / Finding / Caveman output; raw artifact
pointers don't expose content; version-gated Kyverno behavior.
