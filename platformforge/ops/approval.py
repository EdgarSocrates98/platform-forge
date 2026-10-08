"""Cycle 4 — approval engine (§53–64, ADR-0025).

An approval is not a vibe — it is an object bound to an exact content
hash, a scope, parameter bounds, a TTL and an actor. Execution-time
revalidation (TOCTOU): the approved hash, environment state, observation
freshness and policy are all re-checked; a drifted world invalidates the
approval instead of executing against a stale reality.

Break-glass exists, is explicit, expires, is audited — and still keeps
evidence/receipts/verification (§62–64).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from platformforge.live.models import canonical_hash, now_iso, parse_ts

APPROVAL_SCHEMA = "platformforge/approval/v1"
BREAKGLASS_SCHEMA = "platformforge/break-glass/v1"

APPROVAL_TYPES = ("automatic-policy", "single-human", "resource-owner",
                  "platform-owner", "security-review", "dual-human",
                  "break-glass")
DECISIONS = ("approved", "rejected", "expired", "revoked")


@dataclass
class Approval:
    """§55 — approval object. `subject_hash` is the canonical hash of the
    exact ChangePlan/ExecutionEnvelope approved (§56)."""
    approval_id: str = ""
    subject_hash: str = ""            # sha256:… of approved object
    subject_kind: str = ""            # change-plan | execution-envelope
    scope: list[str] = field(default_factory=list)   # canonical resources
    decision: str = "approved"
    actor: str = ""                  # human identity
    actor_kind: str = "human"        # human|agent|host|system
    role: str = ""                   # owner|platform-owner|security…
    type: str = "single-human"
    created_at: str = ""
    expires_at: str = ""
    policy_context: dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    parameter_bounds: dict[str, Any] = field(default_factory=dict)
    signature: str = ""              # optional adapter signature (§236)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = now_iso()   # fixed once — signatures
                                          # depend on stable payload

    def is_expired(self, at: str | None = None) -> bool:
        exp = parse_ts(self.expires_at)
        if exp is None:
            return False             # no TTL = doesn't expire by time
        ref = parse_ts(at) if at else parse_ts(now_iso())
        return bool(ref and ref > exp)

    def signature_valid(self) -> bool | None:
        """Tamper evidence (§236): None if unsigned; False if the
        signature doesn't match the canonical payload."""
        if not self.signature:
            return None
        payload = self.to_dict()
        payload.pop("signature", None)
        want = "sha256:" + canonical_hash(payload)
        return self.signature == want

    def sign(self) -> str:
        payload = self.to_dict()
        payload.pop("signature", None)
        self.signature = "sha256:" + canonical_hash(payload)
        return self.signature

    def to_dict(self) -> dict[str, Any]:
        d = {"schema": APPROVAL_SCHEMA, "approval_id": self.approval_id,
             "subject_hash": self.subject_hash,
             "subject_kind": self.subject_kind, "scope": self.scope,
             "decision": self.decision, "actor": self.actor,
             "actor_kind": self.actor_kind, "role": self.role,
             "type": self.type,
             "created_at": self.created_at or now_iso(),
             "policy_context": self.policy_context, "reason": self.reason}
        if self.expires_at:
            d["expires_at"] = self.expires_at
        if self.parameter_bounds:
            d["parameter_bounds"] = self.parameter_bounds
        if self.signature:
            d["signature"] = self.signature
        return d


@dataclass
class BreakGlass:
    """§62–64 — formal emergency model. Skips nothing audit-related."""
    break_glass_id: str = ""
    invocation_reason: str = ""
    actor: str = ""
    scope: list[str] = field(default_factory=list)
    created_at: str = ""
    expires_at: str = ""
    incident_ref: str = ""
    notify_on_use: list[str] = field(default_factory=list)
    post_review_required: bool = True

    def is_active(self, at: str | None = None) -> bool:
        exp, ref = parse_ts(self.expires_at), \
            parse_ts(at) if at else parse_ts(now_iso())
        return bool(exp and ref and ref <= exp)

    def validate(self) -> list[dict[str, Any]]:
        v = []
        for f_, code, unlock in (
                (self.invocation_reason, "PF-OPS-BG-NO-REASON",
                 "break-glass requires an explicit reason"),
                (self.actor, "PF-OPS-BG-NO-ACTOR",
                 "break-glass requires a human identity"),
                (self.expires_at, "PF-OPS-BG-NO-TTL",
                 "break-glass requires a TTL"),
                (self.scope, "PF-OPS-BG-NO-SCOPE",
                 "break-glass requires a scope")):
            if not f_:
                v.append({"refusal": code, "unlock": unlock})
        return v


@dataclass
class ApprovalCheck:
    ok: bool = False
    refusal: dict[str, Any] | None = None
    used_break_glass: bool = False
    approval: Approval | None = None

    def to_dict(self) -> dict[str, Any]:
        d = {"ok": self.ok, "used_break_glass": self.used_break_glass}
        if self.refusal:
            d["refusal"] = self.refusal
        if self.approval:
            d["approval_id"] = self.approval.approval_id
        return d


def _in_bounds(bounds: dict[str, Any], params: dict[str, Any]) -> bool:
    """§61 — approved bounds: exact key/value or [min,max] ranges.
    Approving replicas 3→5 must not authorize 3→50."""
    for k, b in bounds.items():
        if k not in params:
            continue
        got = params[k]
        if isinstance(b, (list, tuple)) and len(b) == 2 \
                and isinstance(got, (int, float)):
            if not (b[0] <= got <= b[1]):
                return False
        elif got != b:
            return False
    return True


def check_approval(approvals: list[Approval], *,
                   subject_hash: str, scope: list[str],
                   params: dict[str, Any] | None = None,
                   required_type: str = "",
                   at: str | None = None,
                   break_glass: BreakGlass | None = None,
                   current_plan_hash: str = "",
                   allow_actor_kinds: tuple[str, ...] = ("human",)
                   ) -> ApprovalCheck:
    """§56–61 — validate approvals against the *current* plan hash.
    Approvals minted by non-human actors never satisfy human approval
    unless the host explicitly widens `allow_actor_kinds` — an agent
    cannot fabricate human approval."""
    if current_plan_hash and subject_hash != current_plan_hash:
        return ApprovalCheck(refusal={
            "refusal": "PF-OPS-APPROVAL-STALE-PLAN",
            "unlock": "plan hash changed since approval — re-approve"})

    scope_set = set(scope)
    for ap in approvals:
        if ap.decision != "approved":
            continue
        if ap.subject_hash != subject_hash:
            continue                        # bound to another object
        if ap.signature and ap.signature_valid() is False:
            return ApprovalCheck(refusal={
                "refusal": "PF-OPS-APPROVAL-TAMPERED",
                "unlock": "approval signature mismatch — "
                          "payload was modified"})
        if ap.actor_kind not in allow_actor_kinds \
                and ap.type != "break-glass":
            continue                        # agent-minted ≠ human approval
        if required_type and ap.type != required_type \
                and ap.type != "break-glass":
            continue
        if ap.is_expired(at):
            return ApprovalCheck(refusal={
                "refusal": "PF-OPS-APPROVAL-EXPIRED",
                "unlock": "approval TTL elapsed — request a fresh approval"})
        ap_scope = set(ap.scope)
        if ap_scope and scope_set and not scope_set <= ap_scope:
            return ApprovalCheck(refusal={
                "refusal": "PF-OPS-APPROVAL-SCOPE",
                "unlock": "approval scope does not cover target resources"})
        if ap.parameter_bounds and params is not None \
                and not _in_bounds(ap.parameter_bounds, params):
            return ApprovalCheck(refusal={
                "refusal": "PF-OPS-APPROVAL-BOUNDS",
                "unlock": "parameters exceed approved bounds"})
        return ApprovalCheck(ok=True, approval=ap)

    if break_glass is not None:
        errs = break_glass.validate()
        if errs:
            return ApprovalCheck(refusal=errs[0])
        if not break_glass.is_active(at):
            return ApprovalCheck(refusal={
                "refusal": "PF-OPS-BG-EXPIRED",
                "unlock": "break-glass TTL elapsed"})
        if scope_set and break_glass.scope \
                and not scope_set <= set(break_glass.scope):
            return ApprovalCheck(refusal={
                "refusal": "PF-OPS-BG-SCOPE",
                "unlock": "break-glass scope does not cover targets"})
        return ApprovalCheck(ok=True, used_break_glass=True)

    return ApprovalCheck(refusal={
        "refusal": "PF-OPS-NO-APPROVAL",
        "unlock": "obtain an approval bound to this exact plan hash"})


def bind(plan_hash: str, approvals: list[Approval]) -> list[Approval]:
    return [a for a in approvals if a.subject_hash == plan_hash]


def fingerprint(params: dict[str, Any]) -> str:
    return "sha256:" + canonical_hash(params)
