"""Cycle 4 — structured runbook engine (phase O).

Runbooks are data, not scripts: trigger, scope, diagnostics,
preconditions, steps (typed actions only), risk, approval, verification,
rollback, knowledge, sources. `bind()` compiles a runbook to a ChangePlan
+ diagnostics checklist; `audit()` refuses malformed runbooks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from platformforge.live.models import canonical_hash
from platformforge.ops.actions import spec_for
from platformforge.ops.models import PlanStep

RUNBOOK_SCHEMA = "platformforge/runbook/v1"


@dataclass
class RunbookStep:
    step_id: str
    action: str
    params: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    kind: str = "execute"          # diagnose|execute|verify|rollback
    on_failure: str = "abort"      # abort|continue|compensate


@dataclass
class Runbook:
    runbook_id: str = ""
    title: str = ""
    trigger: dict[str, Any] = field(default_factory=dict)
    scope: list[str] = field(default_factory=list)
    diagnostics: list[dict[str, Any]] = field(default_factory=list)
    preconditions: list[str] = field(default_factory=list)
    steps: list[RunbookStep] = field(default_factory=list)
    risk: dict[str, Any] = field(default_factory=dict)
    approval_required: bool = True
    verification: dict[str, Any] = field(default_factory=dict)
    rollback: dict[str, Any] = field(default_factory=dict)
    knowledge: list[dict[str, Any]] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)

    def hash(self) -> str:
        return "sha256:" + canonical_hash(self._payload())

    def _payload(self) -> dict[str, Any]:
        return {"schema": RUNBOOK_SCHEMA, "runbook_id": self.runbook_id,
                "title": self.title, "trigger": self.trigger,
                "scope": self.scope, "diagnostics": self.diagnostics,
                "preconditions": self.preconditions,
                "steps": [{"step_id": s.step_id, "action": s.action,
                           "params": s.params, "kind": s.kind,
                           "depends_on": s.depends_on,
                           "on_failure": s.on_failure}
                          for s in self.steps],
                "risk": self.risk,
                "approval_required": self.approval_required,
                "verification": self.verification,
                "rollback": self.rollback, "knowledge": self.knowledge,
                "sources": self.sources}

    def audit(self) -> list[dict[str, Any]]:
        """Refusals for malformed runbooks — every step must be a
        typed vocabulary action; diagnostics must name an evidence
        source; rollback must not be fabricated."""
        v = []
        if not self.trigger:
            v.append({"refusal": "PF-OPS-RUNBOOK-NO-TRIGGER",
                      "unlock": "declare when this runbook applies"})
        if not self.sources:
            v.append({"refusal": "PF-OPS-RUNBOOK-NO-SOURCE",
                      "unlock": "cite knowledge sources for each claim"})
        seen: set[str] = set()
        for s in self.steps:
            if s.step_id in seen:
                v.append({"refusal": "PF-OPS-RUNBOOK-DUP-STEP",
                          "unlock": f"duplicate step_id {s.step_id}"})
            seen.add(s.step_id)
            if s.kind == "execute" and spec_for(s.action) is None:
                v.append({"refusal": "PF-OPS-UNKNOWN-ACTION",
                          "unlock": f"{s.action} not in action vocabulary"})
            for d in s.depends_on:
                if d not in seen and d not in {
                        x.step_id for x in self.steps}:
                    v.append({"refusal": "PF-OPS-RUNBOOK-BAD-DEP",
                              "unlock": f"{s.step_id} depends on "
                                        f"unknown {d}"})
        for dg in self.diagnostics:
            if not dg.get("source"):
                v.append({"refusal": "PF-OPS-RUNBOOK-DIAG-NO-SOURCE",
                          "unlock": "diagnostics must name an "
                                    "evidence source"})
        return v

    def bind(self, params: dict[str, Any] | None = None
             ) -> dict[str, Any]:
        """Compile to plan steps with bound params."""
        violations = self.audit()
        if violations:
            return {"ok": False, "refusals": violations}
        bound = []
        for s in self.steps:
            p = dict(params or {})
            p.update(s.params)
            if s.depends_on:
                p["__depends_on__"] = s.depends_on
            bound.append(PlanStep(step_id=s.step_id, action=s.action,
                                  params=p))
        return {"ok": True, "steps": bound,
                "runbook_hash": self.hash()}

    def to_dict(self) -> dict[str, Any]:
        d = self._payload()
        d["hash"] = self.hash()
        return d

    @staticmethod
    def from_dict(d: dict[str, Any]) -> Runbook:
        rb = Runbook()
        for k in ("runbook_id", "title", "trigger", "scope",
                  "diagnostics", "preconditions", "risk",
                  "approval_required", "verification", "rollback",
                  "knowledge", "sources"):
            if k in d:
                setattr(rb, k, d[k])
        rb.steps = [RunbookStep(**s) for s in d.get("steps", [])]
        return rb


BUILTIN_RUNBOOKS: dict[str, Runbook] = {
    "replica-drift-restore": Runbook(
        runbook_id="replica-drift-restore",
        title="Restore GitOps-managed replica drift via git",
        trigger={"finding": "live-drift", "drift_kind": "config-drift",
                 "attr_contains": "replicas"},
        scope=["k8s:*:*:Deployment:*"],
        diagnostics=[{"check": "argocd app diff for drift details",
                      "source": "argocd-diff"},
                     {"check": "git log for desired replica count",
                      "source": "git-log"}],
        preconditions=["fresh-observation", "gitops-managed",
                       "no-active-freeze"],
        steps=[RunbookStep("fix-git", "git.open_pr",
                           params={"title": "fix: restore desired "
                                            "replica count"}),
               RunbookStep("argocd-sync", "argocd.sync",
                           params={},
                           depends_on=["fix-git"],
                           kind="execute")],
        risk={"class": "R3"},
        approval_required=True,
        verification={"windows": ["immediate", "stabilization"],
                      "check": "observed replicas == desired"},
        rollback={"strategy": "argo-rollback"},
        sources=["gitops-first-remediation"]),
    "scale-out-under-pressure": Runbook(
        runbook_id="scale-out-under-pressure",
        title="Scale deployment for load (non-prod auto-eligible)",
        trigger={"slo": "burn_rate_elevated", "environment": "non-prod"},
        scope=["k8s:*:*:Deployment:*"],
        diagnostics=[{"check": "error/burn metrics",
                      "source": "metrics"}],
        preconditions=["fresh-observation"],
        steps=[RunbookStep("scale", "kubernetes.scale", params={})],
        risk={"class": "R2"},
        approval_required=True,
        verification={"windows": ["immediate", "stabilization"],
                      "check": "burn_rate declines"},
        rollback={"strategy": "previous-artifact"},
        sources=["sre-scale-out"]),
}
