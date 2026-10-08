"""Cycle 4 — operation state machine + append-only ledger + locks
(§87–106, ADR-0026).

An Operation is an explicit FSM — `draft → planned → … → converged |
failed | rolled-back | …` — never a mutable status string. Invalid
transitions refuse. Every transition appends a hash-chained receipt to
the OperationLedger (`seq` + `prev_hash`, git-style — tamper-evident,
replayable). Locks are per canonical resource; conflicting operations
block, queue or arbitrate — never run side by side. Idempotency keys
dedup retries; resume replays the ledger instead of re-executing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from platformforge.live.models import canonical_hash, now_iso

STATES = ("draft", "planned", "simulated", "policy-reviewed",
          "awaiting-approval", "approved", "scheduled", "executing",
          "verifying", "converged", "partially-converged", "failed",
          "rollback-planned", "rolling-back", "rolled-back",
          "regressed", "cancelled", "expired", "unresolved")

TERMINAL = {"converged", "cancelled", "expired", "rolled-back"}

# §90 — the only legal edges. Anything else → PF-OPS-BAD-TRANSITION.
TRANSITIONS: dict[str, set[str]] = {
    "draft": {"planned", "cancelled"},
    "planned": {"simulated", "policy-reviewed", "cancelled"},
    "simulated": {"policy-reviewed", "planned", "cancelled"},
    "policy-reviewed": {"awaiting-approval", "approved", "cancelled",
                        "planned"},
    "awaiting-approval": {"approved", "cancelled", "expired"},
    "approved": {"scheduled", "executing", "expired", "cancelled"},
    "scheduled": {"executing", "expired", "cancelled"},
    "executing": {"verifying", "failed", "partially-converged",
                  "rolling-back"},
    "verifying": {"converged", "partially-converged", "regressed",
                  "failed", "rollback-planned"},
    "converged": set(),
    "partially-converged": {"verifying", "rollback-planned",
                            "converged", "unresolved"},
    "failed": {"rollback-planned", "unresolved"},
    "rollback-planned": {"rolling-back", "failed", "unresolved"},
    "rolling-back": {"rolled-back", "failed", "unresolved"},
    "rolled-back": set(),
    "regressed": {"rollback-planned", "unresolved"},
    "cancelled": set(),
    "expired": set(),
    "unresolved": {"planned", "cancelled"},
}

ACTORS = ("human", "agent", "host", "system")

LEDGER_EVENTS = ("intent.created", "plan.created", "simulation.completed",
                 "policy.evaluated", "approval.granted", "approval.denied",
                 "execution.started", "step.started", "step.completed",
                 "step.failed", "verification.started", "verified",
                 "converged", "rollback.started", "rollback.completed",
                 "compensation.started", "compensation.completed",
                 "operation.failed", "operation.cancelled",
                 "operation.expired", "lock.acquired", "lock.released",
                 "resume.attempted", "precondition.failed")


@dataclass
class LedgerEntry:
    seq: int
    event: str
    operation_id: str
    actor: str = "system"             # human|agent|host|system
    at: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    prev_hash: str = "genesis"
    entry_hash: str = ""

    def __post_init__(self):
        if not self.at:
            self.at = now_iso()
        if not self.entry_hash:
            body = {"seq": self.seq, "event": self.event,
                    "operation_id": self.operation_id,
                    "actor": self.actor, "at": self.at,
                    "data": self.data, "prev_hash": self.prev_hash}
            self.entry_hash = "sha256:" + canonical_hash(body)

    def to_dict(self) -> dict[str, Any]:
        return {"seq": self.seq, "event": self.event,
                "operation_id": self.operation_id, "actor": self.actor,
                "at": self.at, "data": self.data,
                "prev_hash": self.prev_hash,
                "entry_hash": self.entry_hash}


class OperationLedger:
    """Append-only, hash-chained (§92–95, §235). Tip is the anchor."""

    def __init__(self):
        self.entries: list[LedgerEntry] = []
        self._tip = "genesis"

    @property
    def tip(self) -> str:
        return self._tip

    def append(self, event: str, operation_id: str, *,
               actor: str = "system", data: dict[str, Any] | None = None
               ) -> LedgerEntry:
        if actor not in ACTORS:
            actor = "system"
        from platformforge.core.redaction import redact_obj
        e = LedgerEntry(seq=len(self.entries) + 1, event=event,
                        operation_id=operation_id, actor=actor,
                        data=redact_obj(dict(data or {})),
                        prev_hash=self._tip)
        self.entries.append(e)
        self._tip = e.entry_hash
        return e

    def for_operation(self, op_id: str) -> list[LedgerEntry]:
        return [e for e in self.entries if e.operation_id == op_id]

    def verify_chain(self) -> bool:
        prev = "genesis"
        for i, e in enumerate(self.entries):
            if e.seq != i + 1 or e.prev_hash != prev:
                return False
            body = {"seq": e.seq, "event": e.event,
                    "operation_id": e.operation_id, "actor": e.actor,
                    "at": e.at, "data": e.data, "prev_hash": e.prev_hash}
            if e.entry_hash != "sha256:" + canonical_hash(body):
                return False
            prev = e.entry_hash
        return True

    def to_dict(self) -> dict[str, Any]:
        return {"entries": [e.to_dict() for e in self.entries],
                "tip": self._tip, "count": len(self.entries)}


@dataclass
class ExecutionStep:
    """§96 — step record with hashes + receipts (saga-aware)."""
    step_id: str = ""
    action: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    status: str = "pending"   # pending|running|completed|failed|skipped
    attempt: int = 0
    compensation: str = ""    # action that compensates this step
    saga_class: str = ""      # compensable|pivot|retryable
    inputs_hash: str = ""
    outputs_hash: str = ""
    started_at: str = ""
    finished_at: str = ""
    receipt: dict[str, Any] = field(default_factory=dict)
    idempotency_key: str = ""

    def key(self, plan_hash: str) -> str:
        """Stripe-style: deterministic key from plan+step content."""
        return "sha256:" + canonical_hash(
            {"plan": plan_hash, "step": self.step_id,
             "action": self.action, "params": self.params})

    def effect_key(self, plan_hash: str) -> str:
        """Side-effect identity — action+params only. Two steps with the
        same effect dedupe to one execution (idempotency gate)."""
        return "sha256:" + canonical_hash(
            {"plan": plan_hash, "action": self.action,
             "params": self.params})


@dataclass
class Operation:
    """§89 — the governed unit of work."""
    operation_id: str = ""
    intent_id: str = ""
    plan_hash: str = ""
    envelope_hash: str = ""
    state: str = "draft"
    actor: str = "system"
    steps: list[ExecutionStep] = field(default_factory=list)
    resources: list[str] = field(default_factory=list)   # lock scope
    history: list[dict[str, Any]] = field(default_factory=list)
    idempotency_key: str = ""
    created_at: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = now_iso()

    def transition(self, to: str, ledger: OperationLedger,
                   actor: str | None = None, data: dict[str, Any] | None = None
                   ) -> dict[str, Any]:
        """§90–91 — valid transitions only; anything else refuses."""
        if to not in STATES:
            return {"refusal": "PF-OPS-UNKNOWN-STATE", "unlock":
                    f"state must be one of {STATES}"}
        if to not in TRANSITIONS.get(self.state, set()):
            return {"refusal": "PF-OPS-BAD-TRANSITION",
                    "unlock": f"{self.state} → {to} is not a valid "
                              f"transition; valid: "
                              f"{sorted(TRANSITIONS.get(self.state, []))}"}
        frm = self.state
        self.state = to
        rec = {"from": frm, "to": to, "at": now_iso()}
        self.history.append(rec)
        ledger.append(f"op.{to}", self.operation_id,
                      actor=actor or self.actor,
                      data={"from": frm, "to": to, **(data or {})})
        return {"ok": True, "from": frm, "to": to, "state": to}

    def to_dict(self) -> dict[str, Any]:
        return {"operation_id": self.operation_id,
                "intent_id": self.intent_id, "plan_hash": self.plan_hash,
                "envelope_hash": self.envelope_hash, "state": self.state,
                "actor": self.actor, "resources": self.resources,
                "idempotency_key": self.idempotency_key,
                "history": self.history,
                "created_at": self.created_at,
                "steps": [{"step_id": s.step_id, "action": s.action,
                           "status": s.status, "attempt": s.attempt}
                          for s in self.steps]}


@dataclass
class OperationLock:
    """§99–100 — per-resource mutual exclusion."""
    resource: str = ""
    operation_id: str = ""
    acquired_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"resource": self.resource,
                "operation_id": self.operation_id,
                "acquired_at": self.acquired_at}


class LockTable:
    """Conflicting operations block/queue/arbitrate — never race."""

    def __init__(self):
        self._locks: dict[str, OperationLock] = {}

    def acquire(self, resources: list[str], op_id: str,
                ledger: OperationLedger | None = None
                ) -> dict[str, Any]:
        held = [r for r in resources
                if r in self._locks
                and self._locks[r].operation_id != op_id]
        if held:
            return {"refusal": "PF-OPS-LOCK-CONFLICT",
                    "unlock": "resources locked by operations "
                              f"{sorted({self._locks[r].operation_id for r in held})} "
                              "— wait, queue, or arbitrate",
                    "held": held}
        for r in resources:
            self._locks[r] = OperationLock(resource=r, operation_id=op_id,
                                           acquired_at=now_iso())
        if ledger:
            ledger.append("lock.acquired", op_id,
                          data={"resources": resources})
        return {"ok": True, "locked": resources}

    def release(self, op_id: str,
                ledger: OperationLedger | None = None) -> list[str]:
        freed = [r for r, l in self._locks.items()
                 if l.operation_id == op_id]
        for r in freed:
            del self._locks[r]
        if ledger and freed:
            ledger.append("lock.released", op_id, data={"resources": freed})
        return sorted(freed)

    def held_by(self, resource: str) -> str | None:
        l = self._locks.get(resource)
        return l.operation_id if l else None


def resume(operation: Operation, ledger: OperationLedger
           ) -> dict[str, Any]:
    """§102 — resume after interruption: replay the ledger, revalidate,
    never blind-reexecute. Steps with a stored completed receipt are
    skipped; running/failed steps must be re-planned."""
    entries = ledger.for_operation(operation.operation_id)
    done_steps = {e.data.get("step_id") for e in entries
                  if e.event == "step.completed"}
    plan_steps = {s.step_id for s in operation.steps}
    dangling = [e.data.get("step_id") for e in entries
                if e.event == "step.completed"
                and e.data.get("step_id") not in plan_steps]
    ledger.append("resume.attempted", operation.operation_id,
                  data={"completed_steps": sorted(done_steps)})
    return {
        "operation_id": operation.operation_id,
        "state": operation.state,
        "completed_steps": sorted(done_steps),
        "pending_steps": sorted(plan_steps - done_steps),
        "dangling_completed": sorted(dangling),
        "requires": (["revalidate-approval", "revalidate-environment",
                     "revalidate-observation-freshness"]
                     if operation.state in ("executing", "verifying",
                                            "rolling-back") else []),
        "note": "no step is re-executed without fresh precondition checks"}


def dedup_check(seen_keys: set[str], key: str) -> bool:
    """§219 — same idempotency key + same params → no duplicate effect."""
    if key in seen_keys:
        return False
    seen_keys.add(key)
    return True
