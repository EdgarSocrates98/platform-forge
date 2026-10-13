# CYCLE 2 — FINAL SECURITY REPORT (§189)

Defensive-analysis posture, verified by property tests — see SECURITY.md
for the mechanism reference.

## Redaction boundary (§16–18, ADR-0005)

`core/redaction.py` is the single engine; enforced at every boundary:

- TokenSave index bodies redacted before FTS insert (+`redaction_receipt`).
- Caveman compress redacts *before* compressing — including mode `off`.
- MCP `call_tool` deep-redacts output before serialization.
- Findings never carry secret values.

Property tests assert a known secret never appears in a ContextPack, an
MCP response, a Finding, or Caveman output. Verified in `test_wave_k.py`.

## Analysis surfaces

| Domain | Surface | Boundary kept |
|---|---|---|
| secrets | `analyze secrets` | labels+locations, never values |
| iam | `analyze iam`, `graph identity-*` | trust/SCP/boundary/OIDC |
| sbom/supply | `analyze sbom|supply` | offline vuln list join |
| kyverno/cosign/slsa | `analyze kyverno|cosign|slsa` | version-aware, shape-only |
| hubble | `analyze hubble` | T0/T1 flows, never mixed w/ T3 config |
| contradiction | `analyze contradictions` | `state.contradiction`, both kept |
| ownership | `analyze ownership` | `ownership.conflicted` |

## Refusal / mutation boundaries (§158–159)

- `change approve|apply` → named refusal (host-side only).
- Non-static lab profiles → refused w/o `--allow-profile` + contract.
- Chaos on `env:production` → refused w/o `--allow-prod`.
- No provider SDK in core; `collect` is dump-only.
- Artifact store raw pointers redact content.

## Bounded MCP output

Oversized results → content-addressed `artifact://sha256/<hash>` refs;
`detail_level` bounds are real; refusals carry a code + unlock.
