"""platform-adversarial-critic — attack the plan before acceptance (§22).

The critic runs BEFORE execution/ship and asks the §22 questions as
deterministic checks over the plan + spec. It does not verify (§23):
it finds ways this could be wrong; the verifier proves or refuses
closure after work.
"""

from __future__ import annotations

from typing import Any

from platformforge.agents.contracts import PlatformTaskSpec
from platformforge.agents.orchestrator import OrchestrationPlan
from platformforge.agents.roster import resolve

_ATTACKS = (
    ("assumption", "What assumption could make this wrong?"),
    ("missing-evidence", "What evidence is missing?"),
    ("fail-open", "Can this fail open?"),
    ("partial-coverage", "Can partial coverage look complete?"),
    ("rollback", "Can rollback fail?"),
    ("source-ownership", "Can source ownership be wrong?"),
    ("regression", "Can this recommendation create regression?"),
)


def _has_verifier(plan: OrchestrationPlan) -> bool:
    return any(resolve(n.agent) and resolve(n.agent).role == "verifier"
               for n in plan.dag)


def _has_reviewer(plan: OrchestrationPlan) -> bool:
    return any(resolve(n.agent) and resolve(n.agent).role == "reviewer"
               for n in plan.dag)


def adversarial_review(plan: OrchestrationPlan,
                       spec: PlatformTaskSpec) -> dict[str, Any]:
    """Return one challenge per attack axis with a status: ok | risk."""
    checks: list[dict[str, Any]] = []

    def add(axis: str, status: str, detail: str) -> None:
        checks.append({"axis": axis, "status": status,
                       "detail": detail})

    # assumption — no evidence requirements means conclusions ride on air
    add("assumption",
        "risk" if not spec.evidence_requirements else "ok",
        "spec declares evidence_requirements"
        if spec.evidence_requirements
        else "spec declares no evidence_requirements — any conclusion "
             "could be invented")

    # missing evidence
    add("missing-evidence",
        "risk" if not spec.acceptance_criteria else "ok",
        "acceptance criteria declared" if spec.acceptance_criteria
        else "no acceptance criteria — closure would be uncheckable")

    # fail-open — is a verifier in the DAG and is it terminal
    add("fail-open",
        "ok" if _has_verifier(plan) else "risk",
        "verifier stage present" if _has_verifier(plan)
        else "no verifier in DAG — run could close unverified")

    # partial coverage — fleet/coverage-scoped tasks need coverage evidence
    needs_cov = spec.scope == "fleet" or any(
        "coverage" in e for e in spec.evidence_requirements)
    add("partial-coverage",
        "risk" if needs_cov and "coverage"
        not in " ".join(spec.evidence_requirements) else "ok",
        "coverage evidence required and declared"
        if needs_cov else "no coverage requirement inferred")

    # rollback — risky specs must demand rollback material
    add("rollback",
        "risk" if spec.risk in ("high", "critical")
        and spec.rollback_requirement == "none" else "ok",
        f"rollback_requirement={spec.rollback_requirement}")

    # source-ownership — mutating caps must be forbidden
    from platformforge.agents.taskspec import MUTATING_CAPS
    missing = [c for c in MUTATING_CAPS
               if c not in spec.forbidden_capabilities]
    add("source-ownership",
        "risk" if missing else "ok",
        "mutating capabilities forbidden"
        if not missing else "forbidden_capabilities missing: "
        + ", ".join(missing))

    # regression — envelope must bound fanout
    add("regression",
        "risk" if plan.envelope.max_fanout > plan.envelope.max_agents
        else "ok",
        f"fanout≤{plan.envelope.max_fanout} agents≤"
        f"{plan.envelope.max_agents}")

    risky = [c for c in checks if c["status"] == "risk"]
    return {"verdict": "risk" if risky else "clear",
            "attacks": checks,
            "open_risks": len(risky),
            "note": "critic attacks before acceptance — the verifier "
                    "still decides closure"}


def pre_mortem(spec: PlatformTaskSpec) -> dict[str, Any]:
    """Spec-level attack surface, before a plan exists (§22 questions)."""
    return {"question": spec.intent,
            "axes": [{"axis": a, "question": q} for a, q in _ATTACKS],
            "note": "run adversarial_review(plan, spec) once a DAG "
                    "exists — a question without a plan is a checklist, "
                    "not a finding"}
