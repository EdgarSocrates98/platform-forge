"""Cycle 4 — safe auto-remediation eligibility (A5 experiments only).

Every condition must be *positively* satisfied — any unknown, missing
evidence, or partial coverage produces `PF-OPS-AUTO-INELIGIBLE` with the
failing checks, never a silent "no". Auto-remediation never applies to
prod, never above R2, never without a verified rollback plan.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from platformforge.live.models import age_seconds, now_iso, parse_ts
from platformforge.ops.risk import RISK_RANK

AUTONOMY_RANK = {"A0": 0, "A1": 1, "A2": 2, "A3": 3, "A4": 4,
                 "A5": 5, "A6": 6}
NON_PROD = {"dev", "staging", "test", "lab", "sandbox"}


@dataclass
class Eligibility:
    eligible: bool = False
    checks: list[dict[str, Any]] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    refusal: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"schema": "platformforge/auto-eligibility/v1",
                "eligible": self.eligible, "checks": self.checks,
                "failed": self.failed, "refusal": self.refusal,
                "evaluated_at": now_iso()}


def _add(e: Eligibility, name: str, ok: bool | None, detail: str = ""):
    """ok=None counts as failed (unknown ≠ pass)."""
    e.checks.append({"check": name, "ok": ok is True, "detail": detail})
    if ok is not True:
        e.failed.append(name)


def evaluate_eligibility(
        *, action: str, risk_class: str, capability_autonomy: str,
        environment: str | None, evidence_tier: str | None,
        observation: dict[str, Any] | None, max_observation_age_s: int,
        source_of_truth: dict[str, Any] | None,
        reversibility: str | None, simulation_outcome: str | None,
        policy_decision: str | None, unresolved_identities: int,
        conflicting_operations: int, verification_available: bool,
        rollback_ready: bool,
        at: str | None = None) -> Eligibility:
    e = Eligibility()
    _add(e, "risk<=R2", bool(risk_class) and RISK_RANK.get(
        risk_class, 9) <= RISK_RANK["R2"], risk_class or "unknown")
    _add(e, "autonomy>=A5", AUTONOMY_RANK.get(
        capability_autonomy or "", -1) >= AUTONOMY_RANK["A5"],
         capability_autonomy or "unknown")
    _add(e, "non-prod", bool(environment) and environment in NON_PROD,
         environment or "unknown")
    _add(e, "high-confidence-evidence",
         evidence_tier in ("strong", "confirmed"),
         evidence_tier or "unknown")
    if observation is None:
        _add(e, "fresh-complete-observation", False, "no observation")
    else:
        age = age_seconds(observation.get("captured_at", ""),
                          parse_ts(at))
        complete = bool((observation.get("coverage") or {}).get(
            "complete"))
        _add(e, "fresh-complete-observation",
             age is not None and age <= max_observation_age_s and complete,
             f"age={age}s complete={complete}")
    sot_status = (source_of_truth or {}).get(
        "status", "resolved" if (source_of_truth or {}).get("resolved")
        else "unresolved")
    sot_ok = bool(source_of_truth) and sot_status == "resolved" and \
        not (source_of_truth or {}).get("requires_human_review")
    _add(e, "source-of-truth-resolved", sot_ok,
         f"{(source_of_truth or {}).get('source', 'unknown')} "
         f"status={sot_status}")
    _add(e, "reversible",
         reversibility in ("fully-reversible", "conditionally-reversible"),
         reversibility or "unknown")
    _add(e, "simulation-passed", simulation_outcome == "pass",
         simulation_outcome or "unknown")
    _add(e, "policy-allow", policy_decision == "allow",
         policy_decision or "unknown")
    _add(e, "no-unresolved-identity", unresolved_identities == 0,
         f"{unresolved_identities} unresolved")
    _add(e, "no-conflicts", conflicting_operations == 0,
         f"{conflicting_operations} conflicting")
    _add(e, "verification-available", verification_available)
    _add(e, "rollback-ready", rollback_ready)
    e.eligible = not e.failed
    if not e.eligible:
        e.refusal = {"refusal": "PF-OPS-AUTO-INELIGIBLE",
                     "unlock": "resolve failed checks or request human "
                               "approval (A4 path)",
                     "failed": e.failed}
    return e
