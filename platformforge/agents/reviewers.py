"""Reviewer machinery — deterministic checklists per reviewer (§51–56).

A reviewer never approves and never re-does the specialist's analysis:
it checks a proposal against a DECLARED checklist and returns
pass|gaps|issues. Gaps are findings with the missing item named.
"""

from __future__ import annotations

from typing import Any

from platformforge.models.base import stable_id

# §51 — the operations safety checklist is data, not vibes
OPS_SAFETY_CHECKLIST = (
    "source-of-truth",        # plan derives from declared SoT
    "risk",                   # risk classed and consistent w/ scope
    "approval",               # required approver named
    "rollback-material",      # rollback plan/artifacts exist
    "expected-delta",         # simulated/expected change measured
    "locks",                  # concurrency/lock story declared
    "idempotency",            # re-apply safe or declared unsafe
    "verification",           # post-change verification step exists
)

ARCHITECTURE_TRIGGERS = (
    "new-subsystem", "new-capability", "new-contract",
    "high-blast-radius", "platform-wide",
)

PRIVACY_SURFACES = (
    "fleet-analytics", "dx-analytics", "federation-export",
    "export", "history",
)


def ops_safety_review(plan: dict[str, Any]) -> dict[str, Any]:
    """plan keys (booleans/dicts): source_of_truth, risk, approver,
    rollback, expected_delta, locks, idempotent, verify.
    Missing/False → gap with the item named."""
    key_of = {"source-of-truth": "source_of_truth", "risk": "risk",
              "approval": "approver", "rollback-material": "rollback",
              "expected-delta": "expected_delta", "locks": "locks",
              "idempotency": "idempotent", "verification": "verify"}
    gaps = [item for item, k in key_of.items() if not plan.get(k)]
    return {"verdict": "pass" if not gaps else "gaps",
            "gaps": gaps, "checked": list(OPS_SAFETY_CHECKLIST),
            "review_id": stable_id("PF-OSR", str(sorted(plan)))}


def security_review(proposal: dict[str, Any]) -> dict[str, Any]:
    """Review a security-affecting proposal. Checks: cited evidence,
    no raw secret fields, IAM/network-exposure deltas declared."""
    issues = []
    if not proposal.get("evidence"):
        issues.append("proposal cites no evidence")
    for k in proposal:
        kl = str(k).lower()
        if any(w in kl for w in ("secret_value", "password",
                                 "token_value", "private_key")):
            issues.append(f"raw secret field present: {k}")
    if proposal.get("touches_iam") and not proposal.get("iam_delta"):
        issues.append("IAM touched without declared delta")
    if proposal.get("touches_exposure") \
            and not proposal.get("exposure_delta"):
        issues.append("network exposure changed without declared delta")
    return {"verdict": "issues" if issues else "pass",
            "issues": issues,
            "review_id": stable_id("PF-SECR", str(sorted(proposal)))}


def architecture_review(proposal: dict[str, Any],
                        blast_radius: int = 0) -> dict[str, Any]:
    """Reviews platform-wide/high-blast proposals. An objection always
    cites blast radius or a violated boundary — never taste."""
    objections = []
    triggers = [t for t in proposal.get("triggers", ())
                if t in ARCHITECTURE_TRIGGERS]
    if blast_radius > 50 and not proposal.get("blast_evidence"):
        objections.append(
            f"blast radius {blast_radius} without evidence")
    if "new-contract" in triggers \
            and not proposal.get("contract_schema"):
        objections.append("new contract without a schema")
    if "new-subsystem" in triggers \
            and not proposal.get("boundary_map"):
        objections.append("new subsystem without a boundary map")
    return {"verdict": "objections" if objections else "pass",
            "triggers": triggers, "objections": objections,
            "review_id": stable_id("PF-ARCH", str(sorted(proposal)),
                                   str(blast_radius))}


def privacy_review(output: dict[str, Any]) -> dict[str, Any]:
    """Check an analytics/federation/export/history output. Aggregation
    is not anonymization; identifiers must be explicitly absent or
    declared in the export policy."""
    exposures = []
    surface = output.get("surface", "export")
    if output.get("identifiers") and not output.get("export_policy"):
        exposures.append("identifiers present without export policy")
    if output.get("per_member") and not output.get("member_consent",
                                                  False) \
            and surface in ("dx-analytics", "history"):
        exposures.append("per-member data on a sensitive surface "
                         "without declared basis")
    if output.get("raw_facts") and surface == "federation-export":
        exposures.append("raw facts on a federation export — "
                         "summaries only")
    return {"verdict": "exposures" if exposures else "pass",
            "surface": surface, "exposures": exposures,
            "review_id": stable_id("PF-PRIV", surface,
                                   str(sorted(output)))}
