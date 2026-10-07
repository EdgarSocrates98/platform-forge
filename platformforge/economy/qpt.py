"""Quality-per-token (§30–§32 + cycle-2.1 §34–50) — measured, not claimed.

Methodology: build a `ContextEnvelope` for the full context and one for the
TokenSave-packed context, serialize BOTH with the same serializer, estimate
tokens on exactly those bytes, then hand each envelope to the same judge.
What is measured is what is evaluated — no off-envelope facts.

Deterministic facts the local engine reads are the *working set*, not model
spend: they land in `deterministic_input_bytes`/`deterministic_fact_count`,
while `model_context_*` counts only bytes a model/agent would receive.

Verdicts: `beneficial` (reduction > 0 AND all quality floors pass),
`optimization_not_beneficial` (reduction exists but quality dropped below a
floor — quality wins over economy), `no_reduction` (pack didn't shrink).
"""

from __future__ import annotations

import time
from typing import Any

from platformforge.economy.envelope import ContextEnvelope
from platformforge.tokensave.budget import Budget
from platformforge.tokensave.index import SearchIndex
from platformforge.tokensave.packs import ContextPackBuilder

DEFAULT_FLOORS = {"finding_recall": 0.98, "evidence_recall": 0.98,
                  "precision": 0.9, "unresolved_recall": 1.0}


def _pr(actual: set[str], predicted: set[str]) -> dict[str, Any]:
    tp = len(actual & predicted)
    return {
        "recall": tp / len(actual) if actual else 1.0,
        "precision": tp / len(predicted) if predicted else 1.0,
        "tp": tp, "fn": len(actual - predicted), "fp": len(predicted - actual),
    }


def _default_judge(versions: dict[str, str] | None):
    from platformforge.models import Fact
    from platformforge.rules import RuleEngine, load_catalog
    from platformforge.resources import data_path
    eng = RuleEngine(load_catalog(data_path("rules", "catalog")),
                     versions=versions)

    def judge(env: ContextEnvelope) -> list[dict[str, Any]]:
        out, _ = eng.evaluate([Fact.from_dict(f) for f in env.facts])
        return [{"rule_id": f.rule_id, "status": f.status,
                 "fact": ev} for f in out for ev in f.evidence]
    return judge


def quality_per_token(*, facts_full: list[dict[str, Any]],
                      findings_full: list[dict[str, Any]],
                      index: SearchIndex, task: str,
                      budget: Budget | None = None,
                      judge=None,
                      floors: dict[str, float] | None = None,
                      versions: dict[str, str] | None = None) -> dict[str, Any]:
    """Compare full-context judgment vs packed-context judgment.

    `judge(ContextEnvelope) -> list[finding-dicts]` — defaults to the rule
    catalog evaluated over `env.facts` (versions-aware).
    """
    floors = floors or DEFAULT_FLOORS
    judge = judge or _default_judge(versions)

    # deterministic working set — local facts are not model spend (§38)
    det = ContextEnvelope(kind="deterministic", facts=facts_full,
                          metadata={"task": task, "variant": "working-set"})

    # baseline = everything the pack could have received: every indexed file
    # body + facts + findings (no duplication: files are raw content, facts
    # are the extracted contract a pack would carry anyway)
    all_files = [{"path": p, "content": index.read(p) or ""}
                 for p in index.by_path("*")]
    full = ContextEnvelope(kind="model", files=all_files,
                           facts=facts_full, findings=findings_full,
                           metadata={"task": task, "variant": "full"})
    builder = ContextPackBuilder(index)
    pack = builder.build(task, budget=budget, facts=facts_full,
                         findings=findings_full)
    if pack["budget_decision"] == "refuse":
        return {"budget_decision": "refuse", "qpt": None,
                "reason": pack["budget_reason"]}

    # packed = what the pack actually delivers: selected file bodies + the
    # fact/finding/rule payloads the pack carries (essential, never dropped)
    packed = ContextEnvelope(
        kind="model",
        files=[{"path": f["path"], "content": index.read(f["path"]) or ""}
               for f in pack["relevant_files"]],
        facts=list(pack.get("facts") or []),
        findings=list(pack.get("findings") or []),
        rules=list(pack.get("rules") or []),
        metadata={"task": task, "variant": "tokensave",
                  "pack_budget": pack.get("budget"),
                  "budget_decision": pack.get("budget_decision")})

    # same serializer + estimator for both sides; judge sees exactly the
    # envelope that was measured
    t0 = time.perf_counter()
    full_res = judge(full)
    t_full = time.perf_counter() - t0
    t0 = time.perf_counter()
    pack_res = judge(packed)
    t_pack = time.perf_counter() - t0

    def viol(rs): return {f["rule_id"] for f in rs if f.get("status") == "violated"}
    def ev(rs):   return {f["fact"] for f in rs if f.get("status") == "violated"}
    def unr(rs):  return {f["rule_id"] for f in rs if f.get("status") == "unresolved"}
    def kept(rs): return {f["rule_id"] for f in rs
                          if f.get("status") in ("violated", "unresolved")}

    fr = _pr(viol(full_res), viol(pack_res))
    evr = _pr(ev(full_res), ev(pack_res))
    # unresolved correctness: every rule unresolved at baseline must keep a
    # non-silent verdict (violated|unresolved) in the packed context
    unres_lost = sorted(unr(full_res) - kept(pack_res))
    unres_recall = 1.0 - (len(unres_lost) / len(unr(full_res))
                          if unr(full_res) else 0.0)

    tokens_full = full.estimated_tokens
    tokens_pack = packed.estimated_tokens
    reduction = (1 - tokens_pack / tokens_full) if tokens_full else 0.0

    floors_ok = {
        "finding_recall": fr["recall"] >= floors["finding_recall"],
        "evidence_recall": evr["recall"] >= floors["evidence_recall"],
        "precision": fr["precision"] >= floors["precision"],
        "unresolved_recall": unres_recall >= floors["unresolved_recall"],
    }
    if reduction <= 0:
        verdict = "no_reduction"
    elif all(floors_ok.values()):
        verdict = "beneficial"
    else:
        verdict = "optimization_not_beneficial"

    return {
        "task": task,
        "baseline": {
            "model_context_bytes": full.byte_size,
            "estimated_tokens": tokens_full,
            "facts": len(full.facts),
            "judge_seconds": round(t_full, 6),
            "findings_violated": sorted(viol(full_res)),
            "findings_unresolved": sorted(unr(full_res)),
        },
        "optimized": {
            "model_context_bytes": packed.byte_size,
            "estimated_tokens": tokens_pack,
            "facts": len(packed.facts),
            "judge_seconds": round(t_pack, 6),
            "findings_violated": sorted(viol(pack_res)),
            "findings_unresolved": sorted(unr(pack_res)),
            "pack_refusals": pack.get("refusals") or [],
        },
        "deterministic": det.ledger_fields(),
        "quality": {
            "finding_recall": fr["recall"], "finding_precision": fr["precision"],
            "evidence_recall": evr["recall"], "evidence_precision": evr["precision"],
            "false_negatives": fr["fn"], "false_positives": fr["fp"],
            "unresolved_recall": round(unres_recall, 4),
            "unresolved_lost": unres_lost,
            "floors": floors, "floors_ok": floors_ok,
        },
        "economy": {
            "token_reduction": round(reduction, 4),
            "byte_reduction": round(
                1 - packed.byte_size / full.byte_size, 4) if full.byte_size else 0.0,
        },
        "verdict": verdict,
        # compat with pre-2.1 readers
        "tokens_full_context": tokens_full, "tokens_packed": tokens_pack,
        "token_reduction": round(reduction, 4),
        "finding_recall": fr["recall"], "finding_precision": fr["precision"],
        "evidence_recall": evr["recall"], "evidence_precision": evr["precision"],
        "facts_full": len(facts_full), "facts_packed": len(packed.facts),
        "floors": floors,
        "quality_gate": "pass" if verdict == "beneficial" else "fail",
    }
