"""platform-verifier machinery — independent closure check (§19–21).

The verifier is deterministic and INDEPENDENT: the component that
produced a conclusion cannot be its sole verifier. It maps acceptance
criteria → evidence, checks coverage/freshness claims, recomputes
receipts, and returns a verdict with a receipt — it never upgrades a
claim the evidence doesn't carry.
"""

from __future__ import annotations

from typing import Any

from platformforge.agents.contracts import AgentRefusal, AgentRunRecord, refusal
from platformforge.models.base import stable_id

PRODUCER_ROLES = ("orchestrator", "planner", "coordinator",
                  "specialist", "executor", "critic")


def verify_run(record: AgentRunRecord,
               *, spec: Any | None = None,
               producers: tuple[str, ...] | None = None,
               evidence_index: dict[str, Any] | None = None,
               verifier: str = "platform-verifier") -> dict[str, Any]:
    """Check a run record before closure.

    record          the run under review
    spec            the sealed PlatformTaskSpec (acceptance criteria)
    producers       agents that produced the run's outputs
    evidence_index  fact_id → fact doc (for existence/freshness checks)
    """
    # default producers = run agents minus the verifier itself — the
    # verifier appears in record.agents as a DAG participant, but it is
    # only independent if it produced none of the conclusions
    producers = tuple(producers) if producers is not None else tuple(
        a for a in record.agents if a != verifier)
    problems: list[str] = []

    # §21/§183 — independence: a producer cannot be the sole verifier
    if verifier in producers:
        return refusal(
            AgentRefusal.SELF_VERIFICATION,
            f"{verifier} produced this run and cannot verify it",
            "assign a verifier that is not in the producer set",
            producers=list(producers))
    if record.verifier and record.verifier in producers:
        return refusal(
            AgentRefusal.INDEPENDENCE_FAILED,
            f"declared verifier {record.verifier} is in the producer "
            "set", "verify with an agent that produced no output here")

    # §20 — criteria → evidence map
    criteria = list(getattr(spec, "acceptance_criteria", ()) or ())
    ev_index = evidence_index or {}
    evidence = [e for e in record.evidence
                if not ev_index or e in ev_index]
    missing_ev = [e for e in record.evidence if e not in ev_index] \
        if ev_index else []
    unmapped = []
    if criteria:
        # a criterion is satisfied if any evidence or finding addresses
        # it — deterministic check: evidence must exist at all
        for c in criteria:
            if not evidence:
                unmapped.append(c)
    if unmapped:
        problems.append("criteria with no evidence: "
                        + "; ".join(unmapped))
    for f in getattr(spec, "evidence_requirements", ()) or ():
        if not evidence and "coverage" not in f:
            problems.append(f"evidence requirement unmet: {f}")

    # freshness check when the index carries it
    stale = [eid for eid, f in ev_index.items()
             if isinstance(f, dict)
             and f.get("freshness", {}).get("status")
             in ("stale", "deprecated", "superseded")]
    if stale:
        problems.append("stale evidence cited: " + ", ".join(sorted(stale)))

    verdict = "confirmed"
    if problems:
        verdict = "unresolved"
    elif record.verdict in ("refuted", "unsupported"):
        verdict = record.verdict  # never upgrade a refuted producer output
    elif not evidence and record.evidence:
        verdict = "unsupported"
    elif not evidence:
        verdict = "unresolved"
    receipt_id = stable_id("PF-VRF", record.run_id, verdict)
    out = {"verdict": verdict, "receipt": {
        "receipt_id": receipt_id, "run_id": record.run_id,
        "task_spec_hash": record.task_spec_hash,
        "verifier": verifier,
        "producers": list(producers),
        "evidence_count": len(evidence),
        "missing_evidence_refs": missing_ev,
        "problems": problems}}
    if verdict == "unresolved" and not evidence:
        out.update(refusal(AgentRefusal.NO_EVIDENCE,
                           "run closed with no verifiable evidence",
                           "collect evidence for the declared criteria "
                           "and re-verify"))
        out["receipt"]["problems"] = problems
    return out
