"""Cycle 5 Phase E — golden path intelligence (§72–81).

Escape hatches are *platform gap signals*, never developer blame
(§75–76). Comparisons carry caveats — correlation ≠ causality (§78–79).
DX metrics measure platform friction, never individual people
(§144–149, §305).
"""

from __future__ import annotations

from typing import Any

from platformforge.analytics.models import confidence_for_support

ESCAPE_REASONS = ("missing-capability", "insufficient-flexibility",
                  "policy-block", "performance", "cost",
                  "unsupported-runtime", "manual-preference", "unknown")


def golden_path_analytics(requests: list[dict[str, Any]],
                          outcomes: list[dict[str, Any]] | None = None,
                          escapes: list[dict[str, Any]] | None = None,
                          ) -> dict[str, Any]:
    """§73–80 — adoption + friction + escapes + outcome correlation."""
    by_path: dict[str, dict[str, Any]] = {}
    for r in requests:
        p = by_path.setdefault(
            str(r.get("path") or r.get("template") or "unknown"),
            {"requests": 0, "successful": 0, "failed": 0,
             "abandoned": 0, "manual_overrides": 0,
             "approval_waits": [], "retries": 0})
        p["requests"] += 1
        st = r.get("status")
        if st in ("provisioned", "converged", "ready"):
            p["successful"] += 1
        elif st in ("failed", "refused"):
            p["failed"] += 1
        elif st == "abandoned":
            p["abandoned"] += 1
        if r.get("manual_override"):
            p["manual_overrides"] += 1
        if r.get("approval_wait_s"):
            p["approval_waits"].append(r["approval_wait_s"])
        p["retries"] += int(r.get("retries", 0))
    esc_by_path: dict[str, dict[str, int]] = {}
    for e in escapes or []:
        path = str(e.get("path") or "unknown")
        reason = str(e.get("reason") or "unknown")
        if reason not in ESCAPE_REASONS:
            reason = "unknown"
        d = esc_by_path.setdefault(path, {})
        d[reason] = d.get(reason, 0) + 1
    for path, p in by_path.items():
        n = p["requests"] or 1
        p["success_rate"] = round(p["successful"] / n, 3)
        p["escape_reasons"] = esc_by_path.get(path, {})
        p["escapes"] = sum(p["escape_reasons"].values())
        p["friction"] = {
            "failed": p["failed"], "manual_overrides":
            p["manual_overrides"], "retries": p["retries"],
            "median_approval_wait_s": (
                sorted(p["approval_waits"])[len(p["approval_waits"]) // 2]
                if p["approval_waits"] else None)}
        del p["approval_waits"]
        p["sample_size"] = p["requests"]
        p["confidence"] = confidence_for_support(p["requests"])
    # §78–79 — outcome comparison with caveats
    comparison = _compare(by_path, outcomes or [])
    return {"schema": "platformforge/golden-path-analytics/v1",
            "paths": by_path, "comparison": comparison,
            "caveats": ["correlation is not causality",
                        "escape = platform gap signal, not blame",
                        "small samples cap confidence"]}


def _compare(paths: dict[str, dict[str, Any]],
             outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    """Correlate path → deployment quality/ops success/incidents."""
    out: dict[str, Any] = {}
    for o in outcomes:
        path = str(o.get("path") or "unknown")
        d = out.setdefault(path, {"deployments": 0, "incidents": 0,
                                  "rollbacks": 0})
        d["deployments"] += 1
        if o.get("incident"):
            d["incidents"] += 1
        if o.get("rollback"):
            d["rollbacks"] += 1
    for path, d in out.items():
        n = d["deployments"] or 1
        d["incident_rate"] = round(d["incidents"] / n, 3)
        d["rollback_rate"] = round(d["rollbacks"] / n, 3)
        d["confidence"] = confidence_for_support(d["deployments"])
        d["causal_claim"] = False
    return out


def golden_path_recommendations(analytics: dict[str, Any],
                                min_support: int = 3) -> list[dict[str, Any]]:
    """§80 — evidence-backed improvement suggestions only."""
    recs = []
    for path, p in analytics.get("paths", {}).items():
        if p["requests"] < min_support:
            continue
        esc = p.get("escape_reasons", {})
        top_escape = max(esc.items(), key=lambda kv: kv[1], default=None)
        if p["escapes"] >= 3 and top_escape:
            recs.append({
                "path": path, "type": "improve-golden-path",
                "action": {"missing-capability": "add capability",
                           "insufficient-flexibility": "improve default",
                           "policy-block": "reduce approval",
                           "performance": "automate stage",
                           "cost": "improve default",
                           "unsupported-runtime": "add capability",
                           "manual-preference": "change documentation",
                           "unknown": "change documentation"}.get(
                               top_escape[0], "change documentation"),
                "evidence": {"escapes": p["escapes"],
                             "top_reason": top_escape[0],
                             "requests": p["requests"]},
                "confidence": p["confidence"],
                "executes": False})
        fr = p.get("friction", {})
        if fr.get("failed", 0) >= 3:
            recs.append({"path": path, "type": "reduce-friction",
                         "action": "automate stage",
                         "evidence": {"failed": fr["failed"]},
                         "confidence": p["confidence"],
                         "executes": False})
    return recs
