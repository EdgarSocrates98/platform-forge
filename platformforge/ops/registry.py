"""Cycle 4 phase S — operations capability registry + cross-Forge
delegation contract.

Sibling forges may *request* operations; Platform Forge never
auto-approves cross-forge requests — they mint a ChangeIntent and enter
the normal governed pipeline. Each executor capability declares
max_autonomy, approval requirement, mutation, risk ceiling and runtime
availability so the registry can negotiate honestly.
"""

from __future__ import annotations

from typing import Any

from platformforge.ops.actions import catalog

# executor → advertised capability block
EXECUTOR_CAPS: dict[str, dict[str, Any]] = {
    "git": {"max_autonomy": "A4", "mutates": True,
            "approval": "required-for-merge",
            "risk_ceiling": "R3", "runtime_available": False},
    "terraform": {"max_autonomy": "A4", "mutates": True,
                  "approval": "required",
                  "risk_ceiling": "R5", "runtime_available": False},
    "tofu": {"max_autonomy": "A4", "mutates": True,
             "approval": "required",
             "risk_ceiling": "R5", "runtime_available": False},
    "argocd": {"max_autonomy": "A4", "mutates": True,
               "approval": "required",
               "risk_ceiling": "R4", "runtime_available": False},
    "kubernetes": {"max_autonomy": "A5-lab-only", "mutates": True,
                   "approval": "required-for-R3+",
                   "risk_ceiling": "R4", "runtime_available": False},
    "observe": {"max_autonomy": "A1", "mutates": False,
                "approval": "none",
                "risk_ceiling": "R0", "runtime_available": True},
}


def ops_capabilities() -> dict[str, Any]:
    """Machine-readable ops surface for the v3 manifest."""
    per_action: dict[str, Any] = {}
    for name, spec in catalog().items():
        cap = EXECUTOR_CAPS.get(spec["executor"], {})
        per_action[name] = {
            "executor": spec["executor"],
            "risk_class": spec["risk_base"],
            "mutates": spec["mutating"],
            "dry_run": spec["dry_run"],
            "idempotent": spec["idempotent"],
            "rollback_action": spec["rollback_action"],
            "max_autonomy": cap.get("max_autonomy", "A4"),
            "approval": cap.get("approval", "required"),
            "runtime_available": cap.get("runtime_available", False)}
    return {"schema": "platformforge/ops-capabilities/v3",
            "platform_max_autonomy": "A4",
            "a5_scope": "lab/non-prod narrow reversible only",
            "a6": "non-goal",
            "executors": EXECUTOR_CAPS,
            "actions": per_action}


def delegation_contract() -> dict[str, Any]:
    """What a sibling forge may ask for — and what is refused."""
    return {
        "accepts": ["change-intent", "runbook-request",
                    "observation-request", "policy-eval-request"],
        "refuses": ["direct-execution", "approval-minting",
                    "shell-command", "generic-provider-call"],
        "contract": "cross-forge requests mint ChangeIntent + enter "
                    "the governed pipeline; they never skip stages",
        "refusal_code": "PF-OPS-CROSSFORGE-REFUSED"}


def validate_delegate_request(req: dict[str, Any]
                              ) -> dict[str, Any]:
    """Validate an inbound cross-forge request. Returns refusal or a
    normalized ChangeIntent payload."""
    kind = req.get("kind")
    if kind not in delegation_contract()["accepts"]:
        return {"refusal": "PF-OPS-CROSSFORGE-REFUSED",
                "unlock": f"kind must be one of "
                          f"{delegation_contract()['accepts']}"}
    if kind in ("direct-execution", "approval-minting"):
        return {"refusal": "PF-OPS-CROSSFORGE-REFUSED",
                "unlock": "execution and approval are never "
                          "delegatable"}
    if not req.get("requested_by"):
        return {"refusal": "PF-OPS-NO-ACTOR",
                "unlock": "cross-forge requests need a principal"}
    return {"ok": True, "route": "change-intent",
            "requested_by": req["requested_by"]}
