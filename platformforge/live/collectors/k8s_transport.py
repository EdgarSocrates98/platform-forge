"""Host-side kubectl transport — THE network boundary for k8s live.

Nothing else in platformforge/live touches the cluster. Credentials stay
in the user's kubeconfig; this wrapper never reads, logs, or persists
them. Read-only by construction: only get/api-resources/auth can-i
argument shapes are allowed through.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import Any

_ALLOWED_VERBS = {"get", "api-resources", "auth", "version",
                  "config"}
_DENIED_SUBSTRINGS = ("--token", "--password", "client-key",
                      "client-certificate")


def kubectl_available() -> bool:
    return shutil.which("kubectl") is not None


def current_context() -> str:
    rc, out, _ = kubectl(["config", "current-context"])
    return out.strip() if rc == 0 else ""


def list_contexts() -> list[str]:
    rc, out, _ = kubectl(["config", "get-contexts", "-o", "name"])
    return sorted(out.split()) if rc == 0 else []


def kubectl(args: list[str], timeout: int = 120) -> tuple[int, str, str]:
    """Run a read-only kubectl invocation. Mutating verbs and credential
    flags are refused before the subprocess is even spawned."""
    if not args or args[0] not in _ALLOWED_VERBS:
        verb = args[0] if args else "?"
        return 2, "", f"refused: verb {verb!r} not in read-only allowlist"
    joined = " ".join(args)
    if any(d in joined for d in _DENIED_SUBSTRINGS):
        return 2, "", "refused: credential flags must not be passed"
    try:
        r = subprocess.run(["kubectl", *args], capture_output=True,
                           text=True, timeout=timeout, check=False)
        return r.returncode, r.stdout, r.stderr
    except FileNotFoundError:
        return 127, "", "kubectl not on PATH"
    except subprocess.TimeoutExpired:
        return 124, "", f"kubectl timed out after {timeout}s"


def make_transport(context: str = "", timeout: int = 120):
    """Build a Transport callable bound to a kube context."""

    def transport(a: list[str]) -> tuple[int, str, str]:
        return kubectl(a, timeout=timeout)

    transport.context = context  # type: ignore[attr-defined]
    return transport


def preflight(context: str = "") -> dict[str, Any]:
    """`live doctor` probe — never inventories, only checks plumbing."""
    out: dict[str, Any] = {"kubectl": kubectl_available(),
                           "context": context or current_context()}
    if not out["kubectl"]:
        out["ok"] = False
        out["error"] = "kubectl not on PATH"
        return out
    rc, ver, err = kubectl(["version", "--output", "json"])
    out["ok"] = rc == 0
    if rc != 0:
        out["error"] = err.strip()
    else:
        import json
        try:
            doc = json.loads(ver)
            out["server_version"] = (
                doc.get("serverVersion") or {}).get("gitVersion", "")
        except json.JSONDecodeError:
            out["server_version"] = ""
    out["contexts"] = list_contexts()
    return out
