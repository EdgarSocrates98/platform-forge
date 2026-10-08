"""Cycle 4 phase P — Golden Path lifecycle + PlatformRequest.

A PlatformRequest is a governed service request. Its lifecycle is an
explicit state machine:

    request → validate → plan → policy → approve → provision →
    observe → score → upgrade → decommission

Every transition beyond `plan` requires receipts from earlier stages —
policy decision, cost estimate, security review, approval — nothing is
implicitly skipped. Production readiness is deterministic and preserves
unknown ≠ zero (reuses scorecards' axis semantics).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from platformforge.live.models import canonical_hash, now_iso

REQUEST_STATES = ("requested", "validated", "planned",
                  "policy-reviewed", "approved", "provisioned",
                  "observed", "scored", "upgrade-planned",
                  "decommissioned", "rejected")

_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "requested": ("validated", "rejected"),
    "validated": ("planned", "rejected"),
    "planned": ("policy-reviewed", "rejected"),
    "policy-reviewed": ("approved", "rejected"),
    "approved": ("provisioned", "rejected"),
    "provisioned": ("observed",),
    "observed": ("scored",),
    "scored": ("upgrade-planned", "decommissioned"),
    "upgrade-planned": ("policy-reviewed", "decommissioned"),
    "decommissioned": (),
    "rejected": (),
}


@dataclass
class PlatformRequest:
    request_id: str = ""
    requester: str = ""
    team: str = ""
    kind: str = ""                # service|database|cache|pipeline|…
    template: str = ""            # golden-path id
    params: dict[str, Any] = field(default_factory=dict)
    environment: str = ""
    state: str = "requested"
    receipts: list[dict[str, Any]] = field(default_factory=list)
    history: list[dict[str, Any]] = field(default_factory=list)

    def hash(self) -> str:
        return "sha256:" + canonical_hash({
            "request_id": self.request_id, "kind": self.kind,
            "template": self.template, "params": self.params,
            "environment": self.environment, "requester": self.requester})

    def transition(self, to: str, *, receipt: dict[str, Any] | None = None,
                   actor: str = "system") -> dict[str, Any]:
        allowed = _TRANSITIONS.get(self.state, ())
        if to not in allowed:
            return {"refusal": "PF-OPS-REQ-BAD-TRANSITION",
                    "unlock": f"from {self.state} allowed: "
                              f"{allowed or 'none'}",
                    "from": self.state, "to": to}
        # gate checks — receipts required before advancing; the receipt
        # carried by this transition counts (the stage produces it).
        need = _RECEIPT_REQUIREMENTS.get(to, ())
        have = {r.get("kind") for r in self.receipts}
        if receipt:
            have.add(receipt.get("kind"))
        missing = [k for k in need if k not in have]
        if missing:
            return {"refusal": "PF-OPS-REQ-MISSING-RECEIPT",
                    "unlock": f"attach receipts: {missing}",
                    "from": self.state, "to": to}
        self.state = to
        self.history.append({"to": to, "at": now_iso(), "actor": actor,
                             "receipt": (receipt or {}).get("kind", "")})
        if receipt:
            self.receipts.append(receipt)
        return {"ok": True, "state": to}

    def to_change_intent(self, steps: list | None = None):
        """§128–129 — a Golden Path provisions through the *same*
        governed contracts as everything else: emit a ChangeIntent
        that feeds intent → plan → policy → approval → execute.
        There is no parallel provisioning workflow."""
        from platformforge.ops.models import ChangeIntent
        return ChangeIntent(
            intent_id=f"req-{self.request_id}",
            requested_by=self.requester,
            owner=self.team,
            target_resources=list(self.params.get("resources", [])),
            desired_change={"template": self.template,
                            "kind": self.kind,
                            "params": self.params},
            risk_context={"environment": self.environment},
            expected_outcome=f"golden path {self.template} provisioned "
                             f"for {self.team}")

    def to_dict(self) -> dict[str, Any]:
        return {"schema": "platformforge/platform-request/v1",
                "request_id": self.request_id, "requester": self.requester,
                "team": self.team, "kind": self.kind,
                "template": self.template, "params": self.params,
                "environment": self.environment, "state": self.state,
                "hash": self.hash(), "receipts": self.receipts,
                "history": self.history}


# stage → receipt kinds that must exist (prior receipts + the one
# carried by the transition itself)
_RECEIPT_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "validated": ("validation",),
    "planned": ("plan",),
    "policy-reviewed": ("policy-decision",),
    "approved": ("policy-decision", "cost-estimate", "security-review",
                 "approval"),
    "provisioned": ("execution",),
    "observed": ("observation",),
    "scored": ("scorecard",),
}


def validate_request(req: PlatformRequest,
                     templates: dict[str, Any] | None = None
                     ) -> dict[str, Any]:
    """Deterministic request validation — template exists, required
    inputs present + type-checked, environment declared."""
    findings = []
    ok = True
    if not req.requester or not req.team:
        findings.append({"refusal": "PF-OPS-REQ-NO-OWNER",
                         "unlock": "declare requester + team"})
        ok = False
    if req.environment not in ("dev", "staging", "prod", "lab"):
        findings.append({"refusal": "PF-OPS-REQ-BAD-ENV",
                         "unlock": "environment ∈ dev|staging|prod|lab"})
        ok = False
    tpl = (templates or {}).get(req.template)
    if req.template and tpl is None:
        findings.append({"refusal": "PF-OPS-REQ-UNKNOWN-TEMPLATE",
                         "unlock": f"template {req.template} not in "
                                   "golden-path library"})
        ok = False
    elif tpl is not None:
        for inp in tpl.get("inputs", []):
            name = inp.get("name")
            if inp.get("required", True) and name not in req.params:
                findings.append({"refusal": "PF-OPS-REQ-MISSING-INPUT",
                                 "unlock": f"param '{name}' required "
                                           f"by {req.template}"})
                ok = False
    return {"ok": ok, "findings": findings,
            "receipt": {"kind": "validation", "ok": ok,
                        "at": now_iso()}}


def readiness_score(card: dict[str, Any]) -> dict[str, Any]:
    """Production readiness from a scorecard dict: unknown axes are
    listed, never counted as zero. Returns grade + per-axis rollup."""
    axes = card.get("axes", {})
    grades = {a: v.get("grade", "unknown") for a, v in axes.items()}
    unknown = [a for a, g in grades.items() if g == "unknown"]
    failing = [a for a, g in grades.items() if g in ("F", "D")]
    if unknown:
        verdict = "not-ready"     # unknown ≠ ready
    elif failing:
        verdict = "not-ready"
    elif all(g == "A" for g in grades.values()):
        verdict = "ready"
    else:
        verdict = "conditional"
    return {"verdict": verdict, "axes": grades,
            "unknown_axes": unknown, "failing_axes": failing,
            "note": "unknown axes never count as passed"}
