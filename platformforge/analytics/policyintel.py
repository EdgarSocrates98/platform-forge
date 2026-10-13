"""Cycle 5 Phase F — policy intelligence (§49–57).

Policies stop being only enforcement. Analytics are honest: a policy
with many exceptions is *distributed evidence*, not automatically a bad
policy (§52, §392). Recommendations never edit enforcement (§53–54).
"""

from __future__ import annotations

from typing import Any

from platformforge.analytics.models import confidence_for_support

DECISIONS = ("allow", "deny", "require-approval", "require-human",
             "require-owner", "require-dual", "shadow-allow",
             "shadow-deny")


def policy_metrics(decisions: list[dict[str, Any]],
                   exceptions: list[dict[str, Any]] | None = None,
                   overrides: list[dict[str, Any]] | None = None,
                   ) -> dict[str, dict[str, Any]]:
    """§51 — per-policy decision distribution."""
    out: dict[str, dict[str, Any]] = {}
    for d in decisions:
        pol = str(d.get("policy") or d.get("policy_id") or "unknown")
        m = out.setdefault(pol, {"evaluations": 0, "allows": 0,
                                 "denies": 0, "requires_approval": 0,
                                 "shadow_decisions": 0})
        m["evaluations"] += 1
        dec = str(d.get("decision") or "")
        if dec == "allow":
            m["allows"] += 1
        elif dec == "deny":
            m["denies"] += 1
        elif dec.startswith("require"):
            m["requires_approval"] += 1
        if dec.startswith("shadow"):
            m["shadow_decisions"] += 1
    for e in exceptions or []:
        pol = str(e.get("policy") or "unknown")
        m = out.setdefault(pol, {"evaluations": 0, "allows": 0,
                                 "denies": 0, "requires_approval": 0,
                                 "shadow_decisions": 0})
        m.setdefault("exceptions", 0)
        m["exceptions"] += 1
        if e.get("expired"):
            m["expired_exceptions"] = m.get("expired_exceptions", 0) + 1
    for o in overrides or []:
        pol = str(o.get("policy") or "unknown")
        m = out.setdefault(pol, {"evaluations": 0, "allows": 0,
                                 "denies": 0, "requires_approval": 0,
                                 "shadow_decisions": 0})
        m["overrides"] = m.get("overrides", 0) + 1
    for pol, m in out.items():
        m["sample_size"] = m["evaluations"]
        m["confidence"] = confidence_for_support(m["evaluations"])
    return out


def false_positive_candidates(metrics: dict[str, dict[str, Any]],
                              outcomes: dict[str, int] | None = None,
                              min_support: int = 3) -> list[dict[str, Any]]:
    """§52 — `candidate_false_positive` only when frequent exception +
    successful outcome + repeated pattern. Never a bare verdict."""
    out = []
    for pol, m in metrics.items():
        exc = m.get("exceptions", 0)
        succ = (outcomes or {}).get(pol, 0)
        if exc >= min_support and succ >= min_support:
            out.append({
                "policy": pol, "signal": "candidate_false_positive",
                "evidence": {"exceptions": exc,
                             "successful_overrides": succ,
                             "evaluations": m["evaluations"]},
                "confidence": confidence_for_support(min(exc, succ)),
                "verdict": "review-required",   # §53 — never auto-judge
                "limitations": ["exception ≠ false positive",
                                "needs human policy review"]})
    return out


def policy_recommendations(metrics: dict[str, dict[str, Any]],
                           fp_candidates: list[dict[str, Any]]
                           ) -> list[dict[str, Any]]:
    """§54 — tighten/relax/split-scope/warning/exception-pattern.
    `executes: False` always — human review required (§53)."""
    recs = []
    fp_pols = {c["policy"] for c in fp_candidates}
    for pol, m in metrics.items():
        ev = m.get("evaluations", 0)
        if ev == 0:
            recs.append({"policy": pol, "type": "unused-policy",
                         "recommendation": "review",
                         "note": "unused ≠ safe to delete",  # §56
                         "confidence": "low", "executes": False})
            continue
        if pol in fp_pols:
            recs.append({"policy": pol,
                         "recommendation": "add exception pattern",
                         "evidence": {"exceptions": m.get("exceptions", 0)},
                         "confidence": m["confidence"],
                         "executes": False})
        deny_rate = m["denies"] / ev
        if m.get("overrides", 0) >= 3:
            recs.append({"policy": pol, "recommendation": "split scope",
                         "evidence": {"overrides": m["overrides"],
                                      "deny_rate": round(deny_rate, 3)},
                         "confidence": m["confidence"],
                         "executes": False})
        shadow_denies = m.get("shadow_decisions", 0)
        if shadow_denies >= 3:
            recs.append({"policy": pol,
                         "recommendation": "convert to warning",
                         "evidence": {"shadow_decisions": shadow_denies},
                         "confidence": m["confidence"],
                         "executes": False})
    return recs


def policy_drift(configured: list[str],
                 evaluated: list[str]) -> dict[str, Any]:
    """§55 — configured vs actually evaluated."""
    conf, ev = set(configured), set(evaluated)
    return {"configured": sorted(conf), "evaluated": sorted(ev),
            "configured_not_evaluated": sorted(conf - ev),
            "evaluated_not_configured": sorted(ev - conf),
            "drift": bool(conf ^ ev)}


def shadow_analytics(decisions: list[dict[str, Any]]) -> dict[str, Any]:
    """§57 — would_deny/would_allow + affected teams."""
    wd = [d for d in decisions if d.get("decision") == "shadow-deny"]
    wa = [d for d in decisions if d.get("decision") == "shadow-allow"]
    teams = {str(d.get("team")) for d in wd if d.get("team")}
    return {"would_deny": len(wd), "would_allow": len(wa),
            "potential_impact": len(wd),
            "teams_affected": sorted(teams),
            "sample_size": len(decisions)}
