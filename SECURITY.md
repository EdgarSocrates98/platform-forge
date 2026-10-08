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

## Raw vs redacted artifact policy (§89)

Two artifact classes, explicitly separated:

- **raw artifact** — the source file/dump on disk. The host may read it;
  facts cite it by `source`/`location` *pointer only*. Raw content never
  enters facts, findings, receipts, context packs, FTS index, Caveman
  output or MCP responses.
- **redacted artifact** — any content that crosses the boundary
  (index insert, pack file body, compressed text, finding message).
  `redact_text_report` runs first — including `caveman mode=off` —
  and the redaction receipt records only `label`, `count`, `location`
  and a sha256 pattern-set hash (§90). Secret values are never stored
  anywhere in the receipt chain.
- **artifact store (`.platformforge/store/`) is not a vault** — MCP
  oversize results and RTK compacted output are redacted *before*
  persistence, and `rtk expand` re-redacts on read-back (defense in
  depth; `tests/test_wave_k.py` proves both directions).
- **marker caveat (honest limit):** `[REDACTED:<label>:<sha8>]` hashes
  the secret to 8 hex chars so equal secrets correlate across a run —
  but for a *low-entropy* secret (e.g. `password=hunter22`) the marker
  is a prefix oracle enabling dictionary confirmation. Correlation is
  the trade-off; when it matters, treat the marker as sensitive.

Who returns what: analyzers and the index return *pointers* to raw
artifacts; pack/compress/receipt paths return redacted content. A caller
asking for raw file content through a bounded surface gets a refusal
with an unlock path (read it yourself on the host).

## Tests

`tests/test_wave_k.py` + `test_wave_l.py` cover: secret never in
ContextPack / MCP response / Finding / Caveman output; raw artifact
pointers don't expose content; version-gated Kyverno behavior.
`tests/test_redaction.py` covers per-pattern detection (JWT, GitHub/
GitLab/Slack tokens, private key, password kv, connection strings),
receipt purity, index-before-FTS redaction, caveman mode=off, and
false-positive guards (§86–90). `tests/test_offline.py` blocks sockets
at the syscall level — a network attempt in the core pipeline is a test
failure, not a convention (§91).

## Live boundary (Cycle 3)

- **Transports are allowlisted read-only.** kubectl: `get`/
  `api-resources` only. AWS: describe/list/get + `sts
  get-caller-identity`. Mutating verbs and credential-material flags
  (`--token`, `--password`, `--profile` injection, `--kubeconfig` swaps)
  are refused with `PF-REFUSE` before any subprocess runs.
- **Secrets never leave the boundary.** k8s `Secret` normalizes to
  metadata + `data_keys` only (values are never requested). Sensitive
  annotations (`password|secret|token|key|credential|private`,
  substring match — `auth.token` class included) are stripped during
  normalization; property tests
  (`tests/test_live_security_props.py`) scan serialized envelopes
  end-to-end for planted payloads.
- **Minimum access**: `live rbac` emits a ClusterRole scoped to
  collection needs (`--namespaced-only` for Role); `live
  required-permissions` emits the minimum IAM action list. Doctor
  probes map denied calls into `coverage.denied` — permission gaps are
  evidence, not errors.
- **No mutation path**: `live plan` emits plans + approval envelopes;
  there is no `apply` in the core. `--strict` exits 2 if a plan
  contains mutating actions, so CI can gate on it.
- Credentials live on the host — the cluster registry stores context/
  role references, never secrets.
