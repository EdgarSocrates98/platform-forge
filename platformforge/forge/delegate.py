"""Delegation + A2A envelope — cross-forge task handoff with receipts.

Envelope: {envelope, from_forge, to_forge, task, inputs(refs), budget,
evidence_requirements, deadline_s?, reply_to}. Receipts prove the result;
evidence transfers as fact dicts + artifact refs, never prose."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from platformforge.models.base import stable_id


@dataclass
class Delegation:
    from_forge: str
    to_forge: str
    task: str
    inputs: dict[str, Any] = field(default_factory=dict)
    budget: dict[str, Any] = field(default_factory=dict)
    evidence_requirements: list[str] = field(default_factory=list)
    deadline_s: int | None = None

    def validate(self) -> list[str]:
        errs = []
        if not self.task:
            errs.append("task required")
        if self.deadline_s is not None and self.deadline_s <= 0:
            errs.append("deadline_s must be positive")
        if self.budget and "max_tokens" in self.budget \
                and self.budget["max_tokens"] <= 0:
            errs.append("max_tokens must be positive")
        return errs


def build_envelope(d: Delegation) -> dict[str, Any]:
    errs = d.validate()
    if errs:
        return {"refusal": "platform.delegation.invalid", "errors": errs}
    return {
        "envelope": "platformforge/a2a-envelope/v1",
        "delegation_id": stable_id("PF-DLG", d.from_forge, d.to_forge,
                                   d.task, str(time.time_ns())),
        "from_forge": d.from_forge, "to_forge": d.to_forge,
        "task": d.task, "inputs": d.inputs, "budget": d.budget,
        "evidence_requirements": d.evidence_requirements,
        "deadline_s": d.deadline_s,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def verify_envelope(env: dict[str, Any]) -> dict[str, Any]:
    """Accept/reject an incoming A2A envelope. Missing fields → named gaps."""
    missing = [k for k in ("envelope", "from_forge", "to_forge", "task",
                           "delegation_id") if not env.get(k)]
    ok = not missing and env["envelope"] == "platformforge/a2a-envelope/v1"
    return {"accepted": ok, "missing": missing,
            "refusal": None if ok else "platform.envelope.invalid"}


def result_receipt(env: dict[str, Any], result: dict[str, Any],
                   evidence: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Receipt a completed delegation — evidence transfers as facts/refs."""
    return {
        "receipt": "platformforge/result-receipt/v1",
        "delegation_id": env.get("delegation_id"),
        "from_forge": env.get("to_forge"),   # responder
        "to_forge": env.get("from_forge"),
        "status": "completed",
        "result": result,
        "evidence_facts": evidence or [],
        "unresolved": result.get("unresolved", []),
        "receipt_id": stable_id("PF-RCPT", str(env.get("delegation_id")),
                                str(time.time_ns())),
    }
