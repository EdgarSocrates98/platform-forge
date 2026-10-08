"""Cycle 5 — fleet operations analytics (§150–160).

Operation history aggregates: hotspots, recurring remediation (never
blind auto-remediation — §155), recurring incident patterns, unified
fleet timeline.
"""

from __future__ import annotations

from typing import Any

from platformforge.analytics.models import confidence_for_support


def operation_metrics(ops: list[dict[str, Any]]) -> dict[str, Any]:
    """§151 — fleet operation counters."""
    out = {"operations": len(ops), "converged": 0, "rolled_back": 0,
           "failed": 0, "blocked": 0, "manual": 0, "auto_eligible": 0,
           "time_to_converge_s": []}
    for o in ops:
        st = str(o.get("state") or o.get("outcome") or "")
        if st == "converged":
            out["converged"] += 1
        if st in ("rolled-back", "rollback-planned"):
            out["rolled_back"] += 1
        if st == "failed":
            out["failed"] += 1
        if st in ("refused", "blocked"):
            out["blocked"] += 1
        if o.get("manual"):
            out["manual"] += 1
        if o.get("auto_eligible"):
            out["auto_eligible"] += 1
        if o.get("converge_seconds") is not None:
            out["time_to_converge_s"].append(o["converge_seconds"])
    t = sorted(out.pop("time_to_converge_s"))
    out["median_time_to_converge_s"] = t[len(t) // 2] if t else "unknown"
    out["sample_size"] = len(ops)
    out["confidence"] = confidence_for_support(len(ops))
    return out


def operation_hotspots(ops: list[dict[str, Any]],
                       min_count: int = 3) -> list[dict[str, Any]]:
    """§152 — same action repeatedly on the same service = systemic."""
    groups: dict[tuple, int] = {}
    for o in ops:
        key = (str(o.get("action") or "unknown"),
               str(o.get("service") or o.get("subject") or "unknown"))
        groups[key] = groups.get(key, 0) + 1
    return [{"action": a, "service": s, "count": n,
             "signal": "repeated-operation-same-target",
             "confidence": confidence_for_support(n),
             "note": "possible systemic issue — investigate root cause"}
            for (a, s), n in sorted(groups.items(), key=lambda kv: -kv[1])
            if n >= min_count]


def remediation_recurrence(remediations: list[dict[str, Any]],
                           min_count: int = 2) -> list[dict[str, Any]]:
    """§153–155 — same finding + same remediation repeating. Suggests
    root-cause paths; NEVER turns into blind auto-remediation."""
    groups: dict[tuple, list[dict]] = {}
    for r in remediations:
        key = (str(r.get("finding") or "unknown"),
               str(r.get("remediation") or "unknown"))
        groups.setdefault(key, []).append(r)
    suggestions = {"config": "fix root configuration",
                   "golden-path": "improve golden path",
                   "policy": "add policy",
                   "capacity": "improve capacity"}
    out = []
    for (finding, rem), evs in sorted(groups.items()):
        if len(evs) < min_count:
            continue
        target = str(evs[-1].get("category") or "config")
        out.append({"finding": finding, "remediation": rem,
                    "recurrences": len(evs),
                    "evidence": [str(e.get("ref", "")) for e in evs],
                    "suggested_path": suggestions.get(
                        target, "fix root configuration"),
                    "confidence": confidence_for_support(len(evs)),
                    "auto_remediate": False,     # §155
                    "note": "understand recurrence before automating"})
    return out


def incident_patterns(incidents: list[dict[str, Any]],
                      min_support: int = 2) -> list[dict[str, Any]]:
    """§156–158 — recurring incident signatures with linked evidence."""
    groups: dict[str, list[dict]] = {}
    for i in incidents:
        sig = str(i.get("signature") or
                  f"{i.get('service','?')}:{i.get('symptom','?')}")
        groups.setdefault(sig, []).append(i)
    return [{"pattern": sig, "occurrences": len(evs),
             "evidence": [str(e.get("incident_id") or e.get("ref", ""))
                          for e in evs],
             "services": sorted({str(e.get("service"))
                                 for e in evs if e.get("service")}),
             "confidence": confidence_for_support(len(evs)),
             "causal_claim": False}
            for sig, evs in sorted(groups.items())
            if len(evs) >= min_support]


def fleet_timeline(sources: dict[str, list[dict[str, Any]]],
                   limit: int = 200) -> list[dict[str, Any]]:
    """§159–160 — unified cross-source timeline."""
    out = []
    for src, events in sources.items():
        for e in events:
            out.append({"ts": e.get("ts", ""), "source": src,
                        "subject": e.get("subject") or e.get("service")
                        or e.get("id") or "",
                        "type": e.get("type") or e.get("kind") or "",
                        "ref": e.get("ref") or e.get("hash") or ""})
    out.sort(key=lambda e: e["ts"])
    return out[-limit:]
