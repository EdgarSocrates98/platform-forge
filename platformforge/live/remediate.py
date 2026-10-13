"""Remediation planning V3 (cycle §256).

Desired state is the source of truth. Drift events become *planned*
remediation actions; a deterministic simulation predicts the
post-plan drift state; an approval envelope packages plan + simulation
for human sign-off.

**The core never applies.** Every plan ends `awaiting-approval`; any
apply attempt in-core must refuse (PF-REMED-NO-APPLY). Execution is a
host-side decision behind an explicit policy gate.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

SCHEMA = "platformforge/remediation-plan/v1"
ENVELOPE_SCHEMA = "platformforge/approval-envelope/v1"

# drift class → remediation verb
_ACTIONS = {
    "observed-out-of-band": "decide:adopt|remove",
    "observed-orphan": "decide:decommission|adopt",
    "desired-missing-observed": "create-from-desired",
    "planned-not-applied": "apply-planned",
    "config-drift": "apply-desired",
    "security-drift": "apply-desired",
    "policy-drift": "apply-desired",
    "network-drift": "apply-desired",
    "version-drift": "apply-desired",
    "identity-drift": "apply-desired",
    "runtime-undeclared": "declare-runtime",
    "stale-observation": "re-observe",
    "permission-unknown": "grant-read-scope",
    "uncomparable": "re-observe",
    "scope-mismatch": "re-scope",
    "converged": "none",
    "unknown": "investigate",
}

# actions that mutate provider state → require approval;
# informational/decision actions still require sign-off but never exec
_MUTATING = {"apply-desired", "create-from-desired", "apply-planned"}

AUTO_APPLY_REFUSAL = {
    "refusal": "PF-REMED-NO-APPLY",
    "unlock": "remediation executes host-side only, behind an explicit "
              "policy gate — the core emits plans, never mutations"}


def plan_remediation(drift_events: list[dict[str, Any]],
                     *, desired_source: str = "desired") -> dict[str, Any]:
    """drift events → ordered remediation plan. Every action cites the
    drift event + evidence that produced it."""
    actions: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for e in drift_events:
        cls = e.get("drift_class") or e.get("class", "unknown")
        res = e.get("resource") or e.get("resource_id", "?")
        if (res, cls) in seen:
            continue
        seen.add((res, cls))
        verb = _ACTIONS.get(cls, "investigate")
        if verb == "none":
            continue
        act = {
            "action_id": f"act-{len(actions) + 1}",
            "verb": verb,
            "resource": res,
            "drift_class": cls,
            "source_of_truth": desired_source,
            "evidence": e.get("fact_ids") or e.get("evidence") or [],
            "mutating": verb in _MUTATING,
            "risk": ("high" if cls in ("security-drift", "policy-drift",
                                       "identity-drift") else
                     "medium" if verb in _MUTATING else "low"),
            "drift_event": e,
        }
        if cls in ("stale-observation", "permission-unknown",
                   "uncomparable", "scope-mismatch"):
            act["note"] = ("observation uncertainty — collect fresh "
                           "evidence before any mutation")
        actions.append(act)
    order = {"high": 0, "medium": 1, "low": 2}
    actions.sort(key=lambda a: (order[a["risk"]], a["resource"]))
    return {
        "schema": SCHEMA,
        "source_of_truth": desired_source,
        "actions": actions,
        "counts": {
            "actions": len(actions),
            "mutating": sum(1 for a in actions if a["mutating"]),
            "decision_required": sum(1 for a in actions
                                     if a["verb"].startswith("decide:")),
            "observation_first": sum(1 for a in actions
                                     if a["verb"] == "re-observe")},
        "note": "plan only — apply refused in core (PF-REMED-NO-APPLY)"}


def simulate_plan(plan: dict[str, Any],
                  drift_events: list[dict[str, Any]]) -> dict[str, Any]:
    """Predict the post-plan drift state — deterministic, set-based.
    Mutating actions resolve their drift class; decisions and
    re-observe leave the event pending."""
    resolved: set[tuple[str, str]] = set()
    pending: list[dict[str, Any]] = []
    for a in plan.get("actions", []):
        res = a["resource"]
        if a["verb"] in _MUTATING:
            resolved.add((res, a["drift_class"]))
    for e in drift_events:
        key = (e.get("resource") or e.get("resource_id", "?"),
               e.get("drift_class") or e.get("class", "unknown"))
        if key not in resolved:
            pending.append(e)
    return {
        "simulation": {
            "resolved": sorted(f"{r}|{c}" for r, c in resolved),
            "pending_count": len(pending),
            "pending": pending,
            "would_introduce": [],   # plan never creates new resources
            "confidence": ("full" if not pending else "partial"),
            "note": "simulation is set-theoretic — actual provider "
                    "behavior verified by post-apply re-observation"}}


def _plan_hash(plan: dict[str, Any],
               sim: dict[str, Any]) -> str:
    canon = json.dumps({"p": plan.get("actions"),
                        "s": sim.get("simulation", {})
                               .get("resolved")},
                       sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode()).hexdigest()[:16]


def approval_envelope(plan: dict[str, Any],
                      sim: dict[str, Any],
                      *, ttl_hours: int = 24,
                      approvers_required: int = 1) -> dict[str, Any]:
    """Signable envelope — the authorization boundary. Contains plan
    hash + simulation so approval binds to exactly this plan."""
    ph = _plan_hash(plan, sim)
    return {"schema": ENVELOPE_SCHEMA,
            "envelope": {
                "plan_id": f"plan-{ph}",
                "plan_hash": ph,
                "status": "awaiting-approval",
                "approvers_required": approvers_required,
                "approvals": [],
                "expires_at": (datetime.now(timezone.utc)
                               + timedelta(hours=ttl_hours))
                .isoformat().replace("+00:00", "Z"),
                "mutating_actions": plan.get("counts", {})
                .get("mutating", 0),
                "auto_apply": False,
                "apply_refusal": AUTO_APPLY_REFUSAL,
                "note": "approving this envelope does NOT apply — "
                        "execution is host-side, gated, and produces "
                        "its own receipt"}}


def remediate(drift_events: list[dict[str, Any]], **kw) -> dict[str, Any]:
    """Full pipeline: drift → plan → simulation → approval envelope."""
    plan = plan_remediation(drift_events, **kw)
    sim = simulate_plan(plan, drift_events)
    return {**plan, **sim, **approval_envelope(plan, sim)}
