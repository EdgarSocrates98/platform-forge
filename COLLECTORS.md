# COLLECTORS — provider transports

Two collectors, same shape: a host-side subprocess transport that
enforces read-only access, and a pure normalizer that shapes responses
into `Resource` records for the observation envelope.

## Kubernetes (`live/collectors/k8s.py` + `k8s_transport.py`)

- Transport: `kubectl <verb> <type> -o json` via subprocess. Allowlist:
  `get` only (+ `api-resources` discovery). Mutating verbs (`delete`,
  `apply`, `patch`, `edit`, `scale`, `drain`, `create`, `replace`,
  `exec`, `port-forward`, `cp`, `attach`, `label`, `annotate`,
  `rollout undo`, `taint`, `cordon`) are refused with `PF-REFUSE`.
  Credential flags (`--token`, `--password`, `--insecure-skip-tls-verify`
  variants used to smuggle creds) refused.
- Discovery: `kubectl api-resources -o wide` (fallback to a core list).
  Pagination honored via `--limit`/`continue`; `410 Gone` on
  resourceVersion expiry → refetch, cursor reset.
- Secret safety: `Secret` objects normalize to
  `secret/<ns>/<name>` with `data_keys` only — data values are never
  read by the collector (it does not request `secret.data`), and any
  residual sensitive annotation matching `password|secret|token|key|
  credential|private` (substring, case-insensitive) is stripped at the
  boundary.
- RBAC: `live rbac` emits the minimum ClusterRole; `--namespaced-only`
  emits Role+RoleBinding. `live doctor --provider kubernetes` probes
  `kubectl` presence + `auth can-i` for each resource type.

## AWS (`live/collectors/aws.py` + `aws_transport.py`)

- Transport: `aws <service> <op> --output json`. Allowlist of
  describe/list/get calls (EC2, VPC, IAM read, EKS, RDS, Lambda, S3
  metadata, STS `get-caller-identity` preflight). Mutations refused;
  `--profile`/credential-material flags refused.
- Preflight: `sts get-caller-identity` (account id), per-service probe
  under `--deep`; denied calls go into `coverage.denied` with the
  operation name — permission gaps are part of the envelope, not
  exceptions.
- Regions: `--region` repeatable; default = SDK/env resolution on host.
- `live required-permissions` emits the minimum read IAM action list.
- **Change events**: `live changes --collect` pages CloudTrail
  `lookup-events` (read-only) into `live/changes.jsonl` — event-id
  deduped, `--since/--until/--region` scoped, `--gc` trims by
  age/count. Offline replay: `live changes --events-file <json>`.

## Fixtures (`live/fixtures.py`)

`collect_fixture(provider, fixture_dir)` replays recorded responses
through the *same* transport→normalizer code path — evals and lab
exercise real collection logic offline, byte-for-byte deterministic.
