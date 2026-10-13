"""Specialist machinery — the §98/§99 finding contract.

Every specialist finding is a structured record — claim, status,
evidence, coverage, freshness, confidence, limitations, next_action —
never bare prose. `finding()` validates the shape; `grade()` demotes
any status the evidence cannot carry (no evidence → never confirmed).
"""

from __future__ import annotations

from typing import Any

from platformforge.agents.contracts import OUTPUT_STATUSES, AgentRefusal, refusal
from platformforge.models.base import stable_id

# statuses that REQUIRE at least one evidence ref (§98 + §55)
_EVIDENCE_STATUSES = ("confirmed", "supported", "refuted")


def finding(agent: str, claim: str, *, status: str,
            evidence: tuple[str, ...] = (),
            coverage: float | None = None,
            freshness: str = "unresolved",
            confidence: str = "low",
            limitations: tuple[str, ...] = (),
            next_action: str = "") -> dict[str, Any]:
    """One specialist finding. `status` ∈ OUTPUT_STATUSES; evidence
    statuses with no evidence are demoted to `unsupported` with the
    demotion recorded — never silently upgraded (§98)."""
    if status not in OUTPUT_STATUSES:
        return refusal(
            AgentRefusal.HOST_CAPABILITY,
            f"status {status!r} outside OUTPUT_STATUSES",
            "use one of: " + ", ".join(OUTPUT_STATUSES))
    demoted = False
    asked = status
    if status in _EVIDENCE_STATUSES and not evidence:
        demoted = True
        status = "unsupported"
        limitations = tuple(limitations) + (
            "demoted: status required evidence but none was cited",)
    if coverage is not None:
        try:
            coverage = min(max(float(coverage), 0.0), 1.0)
        except (TypeError, ValueError):
            coverage = None
    doc = {"finding_id": stable_id("PF-FND", agent, claim),
           "agent": agent, "claim": claim, "status": status,
           "evidence": list(evidence),
           "coverage": coverage, "freshness": freshness,
           "confidence": confidence,
           "limitations": list(limitations),
           "next_action": next_action}
    if demoted:
        doc["demoted_from"] = asked
        doc["demoted"] = True
    return doc


def grade(findings: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate findings — counts per status; unsupported/absence is
    surfaced, not hidden behind totals (§98)."""
    by_status: dict[str, int] = {}
    demoted = 0
    for f in findings:
        by_status[f.get("status", "unresolved")] = \
            by_status.get(f.get("status", "unresolved"), 0) + 1
        demoted += 1 if f.get("demoted") else 0
    return {"total": len(findings), "by_status": by_status,
            "demoted": demoted,
            "ok": by_status.get("confirmed", 0)
            + by_status.get("supported", 0)
            + by_status.get("refuted", 0) > 0}
