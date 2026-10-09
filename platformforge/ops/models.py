"""Cycle 4 — operational models: ChangeIntent, ChangePlan, ExpectedDelta.

Invariants (§9–23, ADR-0021/0022/0025):
- A ChangeIntent without evidence is refused — `PF-OPS-NO-EVIDENCE`.
- ChangePlan is a DAG, not a list; it describes *what must change*,
  never *how authorized execution happens*.
- Every relevant plan carries an ExpectedDelta: current observed graph
  vs planned result graph, decomposed by dimension — never a score.
- Models are hashable canonical forms; approvals bind to those hashes.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any

from platformforge.live.models import canonical_hash, now_iso, parse_ts

INTENT_SCHEMA = "platformforge/change-intent/v1"
PLAN_SCHEMA = "platformforge/change-plan/v1"
DELTA_SCHEMA = "platformforge/expected-delta/v1"

REASON_TYPES = ("finding", "incident", "drift", "recommendation",
                "request", "maintenance", "security", "cost", "other")
SOT_TYPES = ("gitops", "terraform", "tofu", "crossplane", "helm",
             "declarative-config", "provider-api", "manual", "unknown")
DELTA_DIMENSIONS = ("resources", "dependencies", "identity", "network",
                    "exposure", "security", "availability", "capacity",
                    "slo", "cost", "ownership", "compliance")

_ID_RE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")


def _id_ok(value: str) -> bool:
    return bool(_ID_RE.match(value or ""))


@dataclass
class Reason:
    """Why the change exists — typed, referenced, never free-text only."""
    type: str = "other"
    finding_ids: list[str] = field(default_factory=list)
    incident_ids: list[str] = field(default_factory=list)
    drift_ids: list[str] = field(default_factory=list)
    recommendation_ids: list[str] = field(default_factory=list)
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = {"type": self.type}
        for k in ("finding_ids", "incident_ids", "drift_ids",
                  "recommendation_ids", "detail"):
            v = getattr(self, k)
            if v:
                d[k] = v
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> Reason:
        d = d or {}
        return cls(type=d.get("type", "other"),
                   finding_ids=list(d.get("finding_ids", [])),
                   incident_ids=list(d.get("incident_ids", [])),
                   drift_ids=list(d.get("drift_ids", [])),
                   recommendation_ids=list(d.get("recommendation_ids", [])),
                   detail=d.get("detail", ""))


@dataclass
class SourceOfTruth:
    """Where the resource should actually be changed (§12–17)."""
    type: str = "unknown"
    repository: str = ""
    path: str = ""
    ref: str = ""
    confidence: str = "unknown"      # high | medium | low | unknown
    evidence: list[str] = field(default_factory=list)

    @property
    def resolved(self) -> bool:
        return self.type not in ("", "unknown") and bool(self.evidence)

    def to_dict(self) -> dict[str, Any]:
        d = {"type": self.type}
        for k in ("repository", "path", "ref", "confidence"):
            v = getattr(self, k)
            if v:
                d[k] = v
        if self.evidence:
            d["evidence"] = list(self.evidence)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> SourceOfTruth:
        d = d or {}
        return cls(type=d.get("type", "unknown"),
                   repository=d.get("repository", ""),
                   path=d.get("path", ""), ref=d.get("ref", ""),
                   confidence=d.get("confidence", "unknown"),
                   evidence=list(d.get("evidence", [])))


@dataclass
class ChangeIntent:
    """§9–11 — what we want to change and why. Never *how*."""
    intent_id: str = ""
    created_at: str = ""
    reason: Reason = field(default_factory=Reason)
    target_resources: list[str] = field(default_factory=list)
    target_nodes: list[str] = field(default_factory=list)
    source_of_truth: SourceOfTruth = field(default_factory=SourceOfTruth)
    desired_change: dict[str, Any] = field(default_factory=dict)
    fact_ids: list[str] = field(default_factory=list)
    observation_ids: list[str] = field(default_factory=list)
    risk_context: dict[str, Any] = field(default_factory=dict)
    expected_outcome: str = ""
    owner: str = ""
    requested_by: str = ""
    expires_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = now_iso()

    @property
    def evidence(self) -> dict[str, Any]:
        return {"fact_ids": self.fact_ids,
                "observation_ids": self.observation_ids,
                "finding_ids": self.reason.finding_ids,
                "incident_ids": self.reason.incident_ids,
                "drift_ids": self.reason.drift_ids}

    def validate(self) -> list[dict[str, Any]]:
        """§11 — no evidence → PF-OPS-NO-EVIDENCE refusal (as a list of
        violations; empty means valid)."""
        v: list[dict[str, Any]] = []
        if not self.intent_id or not _id_ok(self.intent_id):
            v.append({"refusal": "PF-OPS-BAD-INTENT-ID",
                      "unlock": "set intent_id matching " + _ID_RE.pattern})
        if not self.target_resources and not self.target_nodes:
            v.append({"refusal": "PF-OPS-NO-TARGET",
                      "unlock": "name canonical resource ids or graph nodes"})
        ev = self.evidence
        if not any(ev.values()):
            v.append({"refusal": "PF-OPS-NO-EVIDENCE",
                      "unlock": "attach fact_ids/observation_ids/finding_ids/"
                                "incident_ids/drift_ids"})
        if self.reason.type not in REASON_TYPES:
            v.append({"refusal": "PF-OPS-BAD-REASON",
                      "unlock": f"reason.type in {REASON_TYPES}"})
        if not self.owner:
            v.append({"refusal": "PF-OPS-NO-OWNER",
                      "unlock": "set owner — accountable human/team"})
        if self.expires_at and parse_ts(self.expires_at) is None:
            v.append({"refusal": "PF-OPS-BAD-EXPIRY",
                      "unlock": "expires_at must be ISO-8601"})
        return v

    def is_expired(self, at: str | None = None) -> bool:
        exp, ref = parse_ts(self.expires_at), parse_ts(at or now_iso())
        return bool(exp and ref and ref > exp)

    def hash(self) -> str:
        return "sha256:" + canonical_hash(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "schema": INTENT_SCHEMA,
            "intent_id": self.intent_id,
            "created_at": self.created_at,
            "reason": self.reason.to_dict(),
            "target": {"canonical_resource_ids": self.target_resources,
                       "graph_nodes": self.target_nodes},
            "source_of_truth": self.source_of_truth.to_dict(),
            "desired_change": self.desired_change,
            "evidence": self.evidence,
            "risk_context": self.risk_context,
            "expected_outcome": self.expected_outcome,
            "owner": self.owner,
            "requested_by": self.requested_by}
        if self.expires_at:
            d["expires_at"] = self.expires_at
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ChangeIntent:
        t = d.get("target", {})
        ev = d.get("evidence", {})
        return cls(
            intent_id=d.get("intent_id", ""),
            created_at=d.get("created_at", ""),
            reason=Reason.from_dict(d.get("reason")),
            target_resources=list(t.get("canonical_resource_ids", [])),
            target_nodes=list(t.get("graph_nodes", [])),
            source_of_truth=SourceOfTruth.from_dict(d.get("source_of_truth")),
            desired_change=dict(d.get("desired_change", {})),
            fact_ids=list(ev.get("fact_ids", [])),
            observation_ids=list(ev.get("observation_ids", [])),
            risk_context=dict(d.get("risk_context", {})),
            expected_outcome=d.get("expected_outcome", ""),
            owner=d.get("owner", ""),
            requested_by=d.get("requested_by", ""),
            expires_at=d.get("expires_at", ""))


@dataclass
class PlanStep:
    """§21 — a node in the ChangePlan DAG."""
    step_id: str = ""
    action: str = ""                    # typed action, e.g. git.apply_patch
    description: str = ""
    depends_on: list[str] = field(default_factory=list)
    params: dict[str, Any] = field(default_factory=dict)
    validation: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = {"step_id": self.step_id, "action": self.action}
        for k in ("description", "depends_on", "params", "validation"):
            v = getattr(self, k)
            if v:
                d[k] = v
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PlanStep:
        return cls(step_id=d.get("step_id", ""), action=d.get("action", ""),
                   description=d.get("description", ""),
                   depends_on=list(d.get("depends_on", [])),
                   params=dict(d.get("params", {})),
                   validation=list(d.get("validation", [])))


@dataclass
class ExpectedDelta:
    """§22–23 — current observed graph vs planned result, per dimension.
    Each dimension is a structured {add, remove, change} projection —
    decomposed evidence, never a single score."""
    adds: dict[str, list[Any]] = field(default_factory=dict)
    removes: dict[str, list[Any]] = field(default_factory=dict)
    changes: dict[str, list[Any]] = field(default_factory=dict)
    unknown_dimensions: list[str] = field(default_factory=list)

    def diff(self, dimension: str) -> dict[str, list[Any]]:
        return {"add": self.adds.get(dimension, []),
                "remove": self.removes.get(dimension, []),
                "change": self.changes.get(dimension, [])}

    @property
    def is_empty(self) -> bool:
        return not (self.adds or self.removes or self.changes)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"schema": DELTA_SCHEMA}
        if self.adds:
            d["adds"] = self.adds
        if self.removes:
            d["removes"] = self.removes
        if self.changes:
            d["changes"] = self.changes
        if self.unknown_dimensions:
            d["unknown_dimensions"] = self.unknown_dimensions
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> ExpectedDelta:
        d = d or {}
        return cls(adds=dict(d.get("adds", {})),
                   removes=dict(d.get("removes", {})),
                   changes=dict(d.get("changes", {})),
                   unknown_dimensions=list(d.get("unknown_dimensions", [])))


@dataclass
class ChangePlan:
    """§18–21 — what must change: DAG of typed steps + ExpectedDelta +
    validation + rollback requirements. Hashable; approvals bind to it."""
    plan_id: str = ""
    intent_id: str = ""
    created_at: str = ""
    steps: list[PlanStep] = field(default_factory=list)
    affected_resources: list[str] = field(default_factory=list)
    source_changes: list[dict[str, Any]] = field(default_factory=list)
    expected_delta: ExpectedDelta = field(default_factory=ExpectedDelta)
    validation: list[str] = field(default_factory=list)
    rollback_requirements: list[str] = field(default_factory=list)
    notes: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = now_iso()

    def validate(self) -> list[dict[str, Any]]:
        v: list[dict[str, Any]] = []
        if not self.plan_id or not _id_ok(self.plan_id):
            v.append({"refusal": "PF-OPS-BAD-PLAN-ID",
                      "unlock": "set plan_id matching " + _ID_RE.pattern})
        if not self.intent_id:
            v.append({"refusal": "PF-OPS-PLAN-NO-INTENT",
                      "unlock": "plan must reference a ChangeIntent"})
        if not self.steps:
            v.append({"refusal": "PF-OPS-EMPTY-PLAN",
                      "unlock": "add typed steps"})
        cycle = self._find_cycle()
        if cycle:
            v.append({"refusal": "PF-OPS-PLAN-CYCLE",
                      "unlock": f"break dependency cycle {'→'.join(cycle)}"})
        missing = sorted({d for s in self.steps for d in s.depends_on
                          if d not in {x.step_id for x in self.steps}})
        if missing:
            v.append({"refusal": "PF-OPS-PLAN-DANGLING-DEP",
                      "unlock": f"unknown depends_on: {missing}"})
        if self.expected_delta.is_empty and not self.steps:
            v.append({"refusal": "PF-OPS-NO-DELTA",
                      "unlock": "declare expected_delta or steps"})
        return v

    def _find_cycle(self) -> list[str]:
        deps = {s.step_id: list(s.depends_on) for s in self.steps}
        state: dict[str, int] = {}
        stack: list[str] = []

        def visit(n: str) -> list[str] | None:
            state[n] = 1
            stack.append(n)
            for m in deps.get(n, []):
                if m not in deps:
                    continue
                if state.get(m) == 1:
                    return stack[stack.index(m):] + [m]
                if state.get(m) is None:
                    r = visit(m)
                    if r:
                        return r
            stack.pop()
            state[n] = 2
            return None

        for sid in deps:
            if state.get(sid) is None:
                r = visit(sid)
                if r:
                    return r
        return []

    def topo_order(self) -> list[str]:
        """Deterministic topological order (deps first, id-sorted)."""
        deps = {s.step_id: set(s.depends_on) for s in self.steps}
        done: set[str] = set()
        order: list[str] = []
        while len(order) < len(self.steps):
            ready = sorted(s for s, ds in deps.items()
                           if ds <= done and s not in done)
            if not ready:            # cycle — validate() reports it
                break
            order.extend(ready)
            done.update(ready)
        return order

    def waves(self) -> list[list[str]]:
        """Execution waves for §98 safe parallelism."""
        deps = {s.step_id: set(s.depends_on) for s in self.steps}
        done: set[str] = set()
        out: list[list[str]] = []
        while len(done) < len(self.steps):
            w = sorted(s for s, ds in deps.items()
                       if ds <= done and s not in done)
            if not w:
                break
            out.append(w)
            done.update(w)
        return out

    def hash(self) -> str:
        return "sha256:" + canonical_hash(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {"schema": PLAN_SCHEMA,
                "plan_id": self.plan_id,
                "intent_id": self.intent_id,
                "created_at": self.created_at,
                "affected_resources": self.affected_resources,
                "source_changes": self.source_changes,
                "steps": [s.to_dict() for s in self.steps],
                "expected_delta": self.expected_delta.to_dict(),
                "validation": self.validation,
                "rollback_requirements": self.rollback_requirements,
                "notes": self.notes}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ChangePlan:
        return cls(plan_id=d.get("plan_id", ""),
                   intent_id=d.get("intent_id", ""),
                   created_at=d.get("created_at", ""),
                   steps=[PlanStep.from_dict(s) for s in d.get("steps", [])],
                   affected_resources=list(d.get("affected_resources", [])),
                   source_changes=list(d.get("source_changes", [])),
                   expected_delta=ExpectedDelta.from_dict(d.get("expected_delta")),
                   validation=list(d.get("validation", [])),
                   rollback_requirements=list(d.get("rollback_requirements", [])),
                   notes=d.get("notes", ""))


def loads_intent(text: str) -> ChangeIntent:
    return ChangeIntent.from_dict(json.loads(text))


def loads_plan(text: str) -> ChangePlan:
    return ChangePlan.from_dict(json.loads(text))


def dumps(obj: ChangeIntent | ChangePlan) -> str:
    return json.dumps(obj.to_dict(), indent=2, sort_keys=True)


def content_id(prefix: str, obj: dict[str, Any]) -> str:
    digest = hashlib.sha256(
        json.dumps(obj, sort_keys=True, default=str).encode()
    ).hexdigest()[:16]
    return f"{prefix}-{digest}"
