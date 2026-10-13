"""Cycle 4 — ExecutionEnvelope (§65–67, ADR-0021/0025).

The envelope is the *exact* set of authorized actions: executor, typed
actions, scope, preconditions, policy decisions, approvals, risk,
expected delta, verification + rollback strategies, idempotency key,
TTL. It is hash-pinned — after `freeze()` (approval binding) any content
change produces a different hash and downstream validation refuses.
Envelopes are minted only when policy allows; they never mint themselves.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from platformforge.live.models import canonical_hash, now_iso, parse_ts
from platformforge.ops.actions import validate_action

ENVELOPE_SCHEMA = "platformforge/execution/v1"


@dataclass
class ExecutionEnvelope:
    execution_id: str = ""
    intent_id: str = ""
    change_plan_hash: str = ""
    executor: str = ""
    actions: list[dict[str, Any]] = field(default_factory=list)  # {action, params, step_id}
    scope: list[str] = field(default_factory=list)
    preconditions: dict[str, Any] = field(default_factory=dict)
    policy_decisions: list[dict[str, Any]] = field(default_factory=list)
    approvals: list[str] = field(default_factory=list)   # approval ids
    risk: dict[str, Any] = field(default_factory=dict)
    expected_delta: dict[str, Any] = field(default_factory=dict)
    verification: dict[str, Any] = field(default_factory=dict)
    rollback: dict[str, Any] = field(default_factory=dict)
    idempotency_key: str = ""
    created_at: str = ""
    expires_at: str = ""
    _frozen_hash: str = field(default="", repr=False, compare=False)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = now_iso()
        if not self.idempotency_key:
            self.idempotency_key = "idem-" + canonical_hash(
                {"intent": self.intent_id, "plan": self.change_plan_hash,
                 "actions": self.actions})[:24]

    def validate(self) -> list[dict[str, Any]]:
        v: list[dict[str, Any]] = []
        if not self.execution_id:
            v.append({"refusal": "PF-OPS-BAD-EXECUTION-ID",
                      "unlock": "set execution_id"})
        if not self.change_plan_hash:
            v.append({"refusal": "PF-OPS-ENVELOPE-NO-PLAN",
                      "unlock": "envelope must bind to a change_plan_hash"})
        if not self.approvals and not self.policy_decisions:
            v.append({"refusal": "PF-OPS-ENVELOPE-UNGOVERNED",
                      "unlock": "envelope requires policy decisions and/or "
                                "approvals — execution is never self-minted"})
        for a in self.actions:
            r = validate_action(a.get("action", ""), a.get("params", {}))
            if r:
                v.append(r)
        if self.expires_at and parse_ts(self.expires_at) is None:
            v.append({"refusal": "PF-OPS-BAD-EXPIRY",
                      "unlock": "expires_at must be ISO-8601"})
        return v

    def hash(self) -> str:
        return "sha256:" + canonical_hash(self.to_dict())

    @property
    def frozen(self) -> bool:
        return bool(self._frozen_hash)

    def freeze(self) -> str:
        """Bind the envelope to its current hash — post-approval the
        object is treated as immutable (§67)."""
        self._frozen_hash = self.hash()
        return self._frozen_hash

    def is_intact(self) -> bool:
        return not self._frozen_hash or self.hash() == self._frozen_hash

    def is_expired(self, at: str | None = None) -> bool:
        exp = parse_ts(self.expires_at)
        ref = parse_ts(at) if at else parse_ts(now_iso())
        return bool(exp and ref and ref > exp)

    def mutating_actions(self) -> list[dict[str, Any]]:
        from platformforge.ops.actions import spec_for
        return [a for a in self.actions
                if (s := spec_for(a.get("action", ""))) and s.mutating]

    def to_dict(self) -> dict[str, Any]:
        from platformforge.core.redaction import redact_obj
        return {"schema": ENVELOPE_SCHEMA,
                "execution_id": self.execution_id,
                "intent_id": self.intent_id,
                "change_plan_hash": self.change_plan_hash,
                "executor": self.executor,
                # action params are redacted at the serialization
                # boundary — an envelope never emits raw secrets
                "actions": redact_obj(self.actions),
                "scope": self.scope, "preconditions": self.preconditions,
                "policy_decisions": self.policy_decisions,
                "approvals": self.approvals, "risk": self.risk,
                "expected_delta": self.expected_delta,
                "verification": self.verification,
                "rollback": self.rollback,
                "idempotency_key": self.idempotency_key,
                "created_at": self.created_at,
                "expires_at": self.expires_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ExecutionEnvelope:
        return cls(
            execution_id=d.get("execution_id", ""),
            intent_id=d.get("intent_id", ""),
            change_plan_hash=d.get("change_plan_hash", ""),
            executor=d.get("executor", ""),
            actions=list(d.get("actions", [])),
            scope=list(d.get("scope", [])),
            preconditions=dict(d.get("preconditions", {})),
            policy_decisions=list(d.get("policy_decisions", [])),
            approvals=list(d.get("approvals", [])),
            risk=dict(d.get("risk", {})),
            expected_delta=dict(d.get("expected_delta", {})),
            verification=dict(d.get("verification", {})),
            rollback=dict(d.get("rollback", {})),
            idempotency_key=d.get("idempotency_key", ""),
            created_at=d.get("created_at", ""),
            expires_at=d.get("expires_at", ""))
