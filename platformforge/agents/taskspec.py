"""TaskSpec lifecycle — the deterministic `platform-task-spec-reviewer`.

Review (§16) validates scope, evidence requirements, risk, rollback,
acceptance criteria, unknowns and operation boundaries BEFORE any
orchestration. A spec that fails review is rejected with notes; a spec
that passes is `reviewed`, then `seal()`ed — sealed specs are
content-hashed so the orchestrator executes exactly what was reviewed.
"""

from __future__ import annotations

from typing import Any

from platformforge.agents.contracts import AgentRefusal, PlatformTaskSpec, refusal

MUTATING_CAPS = ("ops.apply", "ops.approve", "federation.delegate",
                 "change.apply", "cloud.mutate")

# risk levels that force stronger governance on the spec itself
_GOVERNED_RISK = ("high", "critical")


def review(spec: PlatformTaskSpec,
           reviewer: str = "platform-task-spec-reviewer") -> PlatformTaskSpec:
    """draft → reviewed | rejected. Deterministic, explainable notes."""
    if spec.state != "draft":
        return spec  # only drafts are reviewed; caller sees current state
    notes: list[str] = []
    if not spec.intent.strip():
        notes.append("intent is empty — nothing to plan against")
    if not spec.acceptance_criteria:
        notes.append("no acceptance_criteria — verifier would have "
                     "nothing to check")
    if not spec.evidence_requirements:
        notes.append("no evidence_requirements — conclusions would be "
                     "unverifiable")
    if spec.risk in _GOVERNED_RISK:
        if spec.rollback_requirement == "none":
            notes.append(f"risk={spec.risk} requires a declared or "
                         "material-bound rollback requirement")
        missing = [c for c in MUTATING_CAPS
                   if c not in spec.forbidden_capabilities]
        if missing:
            notes.append("risky spec must explicitly forbid: "
                         + ", ".join(missing))
    if spec.autonomy not in ("read-only", "propose", "simulate"):
        notes.append(f"autonomy {spec.autonomy!r} outside read-only/"
                     "propose/simulate — agents never execute")
    if spec.budget not in ("tiny", "small", "standard", "deep",
                           "critical"):
        notes.append(f"unknown budget class {spec.budget!r}")
    if not spec.domains and spec.complexity != "low":
        notes.append("non-trivial spec with no domains — scope is "
                     "unbounded")
    if notes:
        return spec.transition("rejected", reviewer=reviewer,
                               notes=tuple(notes))
    return spec.transition("reviewed", reviewer=reviewer,
                           notes=(("scope/evidence/risk/rollback/"
                                   "criteria validated"),))


def seal(spec: PlatformTaskSpec) -> PlatformTaskSpec | dict[str, Any]:
    """reviewed → sealed. Only sealed specs may orchestrate (§18)."""
    if spec.state == "rejected":
        return refusal(
            AgentRefusal.SPEC_REJECTED,
            "task spec was rejected: " + "; ".join(spec.review_notes),
            "revise the spec against the review notes and re-review")
    if spec.state != "reviewed":
        return refusal(
            AgentRefusal.SPEC_UNSEALED,
            f"spec is {spec.state!r}, expected 'reviewed'",
            "run the task-spec reviewer first")
    return spec.transition("sealed")


def expire(spec: PlatformTaskSpec) -> PlatformTaskSpec:
    return spec.transition("expired")


def require_sealed(spec: PlatformTaskSpec,
                   complex_: bool = True) -> dict[str, Any] | None:
    """§18 — orchestrators refuse unsealed specs for complex work.
    Returns None when OK, else the refusal doc."""
    if spec.state == "sealed":
        return None
    if not complex_ and spec.state == "reviewed":
        return None
    return refusal(
        AgentRefusal.SPEC_UNSEALED,
        f"orchestration requires a sealed TaskSpec (state={spec.state})",
        "platformforge agents plan → review-spec → seal, then dispatch",
        spec_state=spec.state)
