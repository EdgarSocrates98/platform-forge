"""Dynamic live capability availability (cycle §257).

Reports what the live surface can actually do *right now* on this host:
transport present? observations stored? clusters registered? Each verb
gets an explicit availability verdict — nothing is claimed that cannot
be executed. Also emits the credential-boundary contract: credentials
never enter the core; transports refuse credential arguments.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from platformforge.live.store import ObservationStore

VERBS = ("snapshot", "status", "doctor", "reconcile", "rbac",
         "required-permissions", "topology", "clusters", "drift",
         "incident", "plan", "capability")

CREDENTIAL_BOUNDARY = {
    "core_imports_provider_sdk": False,
    "core_reads_env_credentials": False,
    "credentials_persisted": False,
    "transports": {
        "kubernetes": {
            "binary": "kubectl",
            "reads": "kubeconfig via kubectl only — never parsed by core",
            "denied_args": ["--token", "--password", "client-key",
                            "client-certificate"],
            "mutates": False},
        "aws": {
            "binary": "aws",
            "reads": "env/profile/SSO/IRSA via aws CLI only",
            "denied_verbs": "read-only allowlist — write actions "
                            "refused pre-invocation",
            "mutates": False}},
    "note": "credentials are a host concern; the observation store "
            "contains redacted payloads only"}


def _check_transports() -> dict[str, Any]:
    kubectl = shutil.which("kubectl")
    aws = shutil.which("aws")
    return {"kubernetes": {"available": bool(kubectl),
                           "binary": kubectl or "missing"},
            "aws": {"available": bool(aws),
                    "binary": aws or "missing"}}


def availability(repo: str | Path = ".") -> dict[str, Any]:
    """Per-verb availability verdict grounded in host + store state."""
    transports = _check_transports()
    store = ObservationStore(repo)
    obs = store.list(limit=2)
    from platformforge.live.federation import ClusterRegistry
    clusters = ClusterRegistry(repo).list()
    verdicts: dict[str, dict[str, Any]] = {}
    for verb in VERBS:
        ok, reason = True, "ready"
        if verb == "snapshot" and not any(
                t["available"] for t in transports.values()):
            ok, reason = False, "no collector transport in PATH"
        elif verb == "drift" and len(obs) < 2:
            ok, reason = False, "needs ≥2 stored observations"
        elif verb in ("status", "reconcile", "plan") and not obs:
            ok, reason = False, "observation store empty"
        elif verb == "clusters" and not clusters:
            ok, reason = True, "no clusters registered yet"
        verdicts[verb] = {"available": ok, "reason": reason}
    available = sum(1 for v in verdicts.values() if v["available"])
    return {"schema": "platformforge/live-capability/v1",
            "verbs": verdicts,
            "transports": transports,
            "observations": len(obs),
            "clusters_registered": len(clusters),
            "credential_boundary": CREDENTIAL_BOUNDARY,
            "counts": {"verbs": len(VERBS), "available": available,
                       "unavailable": len(VERBS) - available}}
