"""Cycle 4 — mutation risk taxonomy (§31–35, ADR-0024).

Risk classes R0–R5 plus decomposed dimensions — blast radius,
environment, criticality, reversibility, security/identity/network/
data/availability/cost impact, uncertainty, freshness, coverage,
rollback confidence. The load-bearing rule: **unknown ≠ low**. Any
unassessed dimension raises uncertainty, and unknown reversibility or
rollback bumps the class — never downgrades it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

RISK_CLASSES = ("R0", "R1", "R2", "R3", "R4", "R5")
RISK_RANK = {r: i for i, r in enumerate(RISK_CLASSES)}

RISK_DIMENSIONS = ("blast_radius", "environment", "criticality",
                   "reversibility", "security_impact", "identity_impact",
                   "network_exposure", "data_impact", "availability_impact",
                   "cost_impact", "uncertainty", "observation_freshness",
                   "coverage_completeness", "rollback_confidence")

REVERSIBILITY = ("fully-reversible", "conditionally-reversible",
                 "hard-to-reverse", "irreversible", "unknown")

# Per-dimension levels → numeric weight (higher = riskier)
_LEVELS = {"none": 0, "low": 1, "medium": 2, "high": 3,
           "critical": 4, "unknown": 3}

# Action-type → default class ceiling/floor hints (typed actions only —
# see ops/actions.py for the vocabulary).
ACTION_BASE_RISK: dict[str, str] = {
    "git.create_branch": "R0",
    "git.apply_patch": "R1",
    "git.commit": "R1",
    "git.open_pr": "R2",
    "ci.validate": "R0",
    "policy.check": "R0",
    "terraform.validate": "R0",
    "terraform.plan": "R0",
    "terraform.apply_saved_plan": "R3",
    "tofu.plan": "R0",
    "tofu.apply_saved_plan": "R3",
    "argocd.sync": "R3",
    "argocd.rollback": "R3",
    "kubernetes.scale": "R2",
    "kubernetes.rollout_restart": "R2",
    "kubernetes.rollout_undo": "R3",
    "kubernetes.annotate": "R1",
    "k8s.observe": "R0",
    "aws.observe": "R0",
}

# Escalators: contexts that raise class regardless of base.
_DESTRUCTIVE_SIGNALS = ("delete", "destroy", "remove", "drop", "purge")
_IDENTITY_SIGNALS = ("iam", "policy", "role", "permission", "trust")
_DATA_SIGNALS = ("database", "rds", "bucket", "volume", "stateful",
                 "persistent")


@dataclass
class RiskAssessment:
    risk_class: str = "R0"
    dimensions: dict[str, str] = field(default_factory=dict)
    reversibility: str = "unknown"
    escalation_reasons: list[str] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)

    @property
    def blocks_autonomy(self) -> bool:
        """A5 experiments never run above R2 or with unknowns."""
        return RISK_RANK[self.risk_class] > RISK_RANK["R2"] or \
            bool(self.unknowns)

    def to_dict(self) -> dict[str, Any]:
        return {"risk_class": self.risk_class,
                "reversibility": self.reversibility,
                "dimensions": self.dimensions,
                "escalation_reasons": self.escalation_reasons,
                "unknowns": self.unknowns,
                "blocks_autonomy": self.blocks_autonomy}


def assess(action: str, params: dict[str, Any] | None = None,
           context: dict[str, Any] | None = None) -> RiskAssessment:
    """Deterministic risk classification for a typed action.

    `params`   — action params (e.g. {"replicas": 5, "resource": ...})
    `context`  — {environment, criticality, blast_radius, coverage,
                  freshness, reversibility, data_impact, identity_impact,
                  security_impact, network_exposure, cost_impact,
                  rollback_confidence}
    """
    params = params or {}
    ctx = context or {}
    dims: dict[str, str] = {}
    unknowns: list[str] = []
    escalations: list[str] = []

    base = ACTION_BASE_RISK.get(action)
    if base is None:
        base = "R5"
        unknowns.append(f"unlisted-action:{action}")
        escalations.append("unknown action type → R5 ceiling")

    env = ctx.get("environment", "unknown")
    dims["environment"] = env
    if env == "prod" and RISK_RANK[base] < RISK_RANK["R3"]:
        escalations.append("prod environment → ≥R3")
        base = "R3"
    elif env == "unknown":
        unknowns.append("environment")
        dims["environment"] = "unknown"

    rev = ctx.get("reversibility", "unknown")
    if rev not in REVERSIBILITY:
        rev = "unknown"
    if rev == "unknown":
        unknowns.append("reversibility")
    elif rev == "irreversible":
        escalations.append("irreversible → ≥R4")
        if RISK_RANK[base] < RISK_RANK["R4"]:
            base = "R4"
    elif rev == "hard-to-reverse":
        escalations.append("hard-to-reverse → ≥R3")
        if RISK_RANK[base] < RISK_RANK["R3"]:
            base = "R3"
    dims["reversibility"] = rev

    for dim in ("criticality", "blast_radius", "security_impact",
                "identity_impact", "network_exposure", "data_impact",
                "availability_impact", "cost_impact",
                "rollback_confidence", "observation_freshness",
                "coverage_completeness"):
        v = ctx.get(dim, "unknown")
        dims[dim] = v
        if v == "unknown":
            unknowns.append(dim)
        elif v in ("high", "critical"):
            escalations.append(f"{dim}={v}")

    # Content signals — params describing destructive/identity/data ops
    blob = repr(params).lower()
    if any(s in blob for s in _DESTRUCTIVE_SIGNALS):
        escalations.append("destructive signal in params → ≥R4")
        base = "R4" if RISK_RANK[base] < RISK_RANK["R4"] else base
    if any(s in blob for s in _IDENTITY_SIGNALS):
        escalations.append("identity/security surface")
        if ctx.get("identity_impact", "unknown") in ("high", "critical",
                                                   "unknown"):
            base = "R4" if RISK_RANK[base] < RISK_RANK["R4"] else base
    if any(s in blob for s in _DATA_SIGNALS) and \
            ctx.get("data_impact", "unknown") in ("high", "critical"):
        escalations.append("data-critical target")
        base = "R4" if RISK_RANK[base] < RISK_RANK["R4"] else base

    if dims.get("blast_radius") in ("high", "critical"):
        base = "R4" if RISK_RANK[base] < RISK_RANK["R4"] else base
    if dims.get("rollback_confidence") == "unknown":
        escalations.append("rollback confidence unknown")

    return RiskAssessment(risk_class=base, dimensions=dims,
                          reversibility=rev,
                          escalation_reasons=escalations,
                          unknowns=sorted(set(unknowns)))


def classify_reversibility(action: str, params: dict[str, Any] | None = None,
                           context: dict[str, Any] | None = None) -> str:
    """§34–35 — reversibility is assessed, never invented."""
    params = params or {}
    ctx = context or {}
    blob = repr(params).lower()
    if any(s in blob for s in _DESTRUCTIVE_SIGNALS):
        if ctx.get("data_present") or "data" in blob:
            return "irreversible"
        return "hard-to-reverse"
    if action in ("kubernetes.scale", "kubernetes.annotate",
                  "kubernetes.rollout_restart", "git.create_branch"):
        return "fully-reversible"
    if action in ("git.open_pr", "git.apply_patch", "git.commit"):
        return "conditionally-reversible"
    if action in ("terraform.apply_saved_plan", "tofu.apply_saved_plan",
                  "argocd.sync"):
        return ctx.get("reversibility_hint", "conditionally-reversible")
    if action in ("kubernetes.rollout_undo", "argocd.rollback"):
        return "conditionally-reversible"
    return "unknown"
