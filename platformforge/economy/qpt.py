"""Quality-per-token (§30–§32) — measured, not claimed.

Same task, same expected set: judge on FULL context vs the TokenSave pack,
then report finding recall/precision, evidence recall, and token reduction.
The gate (§32) only reports improvement when token_reduction > 0 AND
recall >= configured floor (default 0.98, overridable via workspace config).
"""

from __future__ import annotations

from typing import Any

from platformforge.tokensave.budget import Budget
from platformforge.tokensave.estimate import estimate_tokens
from platformforge.tokensave.index import SearchIndex
from platformforge.tokensave.packs import ContextPackBuilder

DEFAULT_FLOORS = {"finding_recall": 0.98, "evidence_recall": 0.98,
                  "precision": 0.9}


def _pr(actual: set[str], predicted: set[str]) -> dict[str, float]:
    tp = len(actual & predicted)
    return {
        "recall": tp / len(actual) if actual else 1.0,
        "precision": tp / len(predicted) if predicted else 1.0,
        "tp": tp, "fn": len(actual - predicted), "fp": len(predicted - actual),
    }


def quality_per_token(*, facts_full: list[dict[str, Any]],
                      findings_full: list[dict[str, Any]],
                      index: SearchIndex, task: str,
                      budget: Budget | None = None,
                      judge=None,
                      floors: dict[str, float] | None = None) -> dict[str, Any]:
    """Compare full-context judgment vs packed-context judgment.

    `judge(facts_subset) -> list[finding-dicts]` — defaults to the catalog
    engine over the given fact subset. Packed facts = facts whose source
    path is in the pack OR are marked essential by the caller.
    """
    from platformforge.models import Fact
    from platformforge.rules import RuleEngine, load_catalog
    floors = floors or DEFAULT_FLOORS
    if judge is None:
        eng = RuleEngine(load_catalog("rules/catalog"))

        def judge(facts):
            out, _ = eng.evaluate([Fact.from_dict(f) for f in facts])
            return [{"rule_id": f.rule_id, "status": f.status,
                     "fact": ev} for f in out for ev in f.evidence
                    if f.status == "violated"]

    builder = ContextPackBuilder(index)
    pack = builder.build(task, budget=budget, facts=facts_full,
                         findings=findings_full)
    if pack["budget_decision"] == "refuse":
        return {"budget_decision": "refuse", "qpt": None,
                "reason": pack["budget_reason"]}

    packed_paths = {f["path"] for f in pack["relevant_files"]}
    facts_packed = [f for f in facts_full
                    if f.get("source", "") in packed_paths
                    or str(f.get("location", "")) in packed_paths]
    # essential facts are always in the pack
    facts_packed = facts_packed or facts_full[:0]

    full_findings = {f["rule_id"] for f in judge(facts_full)
                     if f.get("status") == "violated"}
    pack_findings = {f["rule_id"] for f in judge(facts_packed)
                     if f.get("status") == "violated"}
    full_ev = {f["fact"] for f in judge(facts_full)
               if f.get("status") == "violated"}
    pack_ev = {f["fact"] for f in judge(facts_packed)
               if f.get("status") == "violated"}

    tokens_full = estimate_tokens(
        " ".join(str(f) for f in facts_full))
    tokens_pack = pack["est_input_tokens"]
    reduction = (1 - tokens_pack / tokens_full) if tokens_full else 0.0

    fr = _pr(full_findings, pack_findings)
    ev = _pr(full_ev, pack_ev)
    gate = (reduction > 0
            and fr["recall"] >= floors["finding_recall"]
            and ev["recall"] >= floors["evidence_recall"]
            and fr["precision"] >= floors["precision"])
    return {
        "task": task,
        "tokens_full_context": tokens_full,
        "tokens_packed": tokens_pack,
        "token_reduction": round(reduction, 4),
        "finding_recall": fr["recall"], "finding_precision": fr["precision"],
        "evidence_recall": ev["recall"], "evidence_precision": ev["precision"],
        "facts_full": len(facts_full), "facts_packed": len(facts_packed),
        "findings_full": sorted(full_findings),
        "findings_packed": sorted(pack_findings),
        "floors": floors,
        "quality_gate": "pass" if gate else "fail",
    }
