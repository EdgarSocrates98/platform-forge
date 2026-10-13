"""Cycle 4 — precondition engine (§87–88).

Every check runs *immediately before* execution: fresh observation,
sufficient coverage, resource still present, hashes unchanged, plan
still valid, owner unchanged, policy still allows, approval still valid,
maintenance window open. Any failure → `PF-OPS-PRECONDITION-FAILED`
with the specific check named — never a blind attempt.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from platformforge.live.models import age_seconds, now_iso, parse_ts


@dataclass
class Precondition:
    name: str = ""
    ok: bool = True
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "ok": self.ok, "detail": self.detail}


def check_preconditions(*,
                        observation: dict[str, Any] | None = None,
                        max_observation_age_s: int = 900,
                        expected_resource_state: dict[str, Any] | None = None,
                        current_resource_state: dict[str, Any] | None = None,
                        plan_hash: str = "", current_plan_hash: str = "",
                        owner: str = "", current_owner: str = "",
                        policy_decision: str = "",
                        approval_valid: bool | None = None,
                        maintenance_window: dict[str, Any] | None = None,
                        freeze_active: bool = False,
                        break_glass: bool = False,
                        at: str | None = None) -> dict[str, Any]:
    """Returns {ok, checks[], refusal?}. Each check is named — a failed
    precondition is an explicit state, never silent."""
    checks: list[Precondition] = []

    if observation is not None:
        age = age_seconds(observation.get("captured_at") or
                          observation.get("collected_at"),
                          parse_ts(at))
        fresh = age is not None and age <= max_observation_age_s
        checks.append(Precondition(
            "observation-fresh", fresh,
            f"age={age:.0f}s limit={max_observation_age_s}s"
            if age is not None else "no timestamp"))
        cov = (observation.get("coverage") or {})
        complete = cov.get("complete", cov.get("status") == "complete")
        checks.append(Precondition("coverage-sufficient", bool(complete),
                                   cov.get("status", "unknown")))
    else:
        checks.append(Precondition("observation-fresh", False,
                                   "no observation supplied"))

    if expected_resource_state is not None:
        same = current_resource_state is not None and \
            expected_resource_state == current_resource_state
        checks.append(Precondition(
            "resource-hash-unchanged", same,
            "resource drifted since plan" if not same else "unchanged"))

    if plan_hash:
        same = plan_hash == current_plan_hash
        checks.append(Precondition("plan-still-valid", same,
                                   "plan hash changed" if not same
                                   else plan_hash[:24]))
    if owner:
        same = owner == current_owner
        checks.append(Precondition("owner-unchanged", same,
                                   f"owner {owner}→{current_owner}"))

    if policy_decision:
        checks.append(Precondition("policy-still-allows",
                                   policy_decision == "allow",
                                   policy_decision))
    if approval_valid is not None:
        checks.append(Precondition("approval-still-valid",
                                   bool(approval_valid)))

    if maintenance_window:
        t = parse_ts(at) if at else parse_ts(now_iso())
        ws, we = (parse_ts(maintenance_window.get("start") or ""),
                  parse_ts(maintenance_window.get("end") or ""))
        open_ = bool(ws and we and t and ws <= t <= we)
        checks.append(Precondition("maintenance-window-open", open_,
                                   f"{maintenance_window.get('start','?')}"
                                   f"→{maintenance_window.get('end','?')}"))

    if freeze_active and not break_glass:
        checks.append(Precondition("change-freeze", False,
                                   "freeze period active (break-glass can "
                                   "override only explicitly)"))

    failed = [c for c in checks if not c.ok]
    out: dict[str, Any] = {"ok": not failed,
                           "checks": [c.to_dict() for c in checks]}
    if failed:
        out["refusal"] = {"refusal": "PF-OPS-PRECONDITION-FAILED",
                          "unlock": "fix failed preconditions then re-plan: "
                                    f"{[c.name for c in failed]}",
                          "failed": [c.name for c in failed]}
    return out
