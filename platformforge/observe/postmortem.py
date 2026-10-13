"""§88/§89 Incident timeline + postmortem engine.

Timeline: merge alerts/changes/logs/k8s events into one canonical,
sorted sequence (§88). Postmortem: draft strictly from evidence —
root cause stays `unresolved` unless a single hypothesis is both
strongly-supported and uncontradicted (§89: never invent a cause).
"""

from __future__ import annotations

from typing import Any

EVENT_KINDS = ("change", "deploy", "alert", "log", "trace", "metric",
               "k8s_event", "cloud_event")


def timeline(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Canonical sorted timeline; every event carries its declared kind
    and source — nothing is reclassified as causal."""
    norm = []
    for e in events:
        norm.append({"at": float(e.get("at") or e.get("ts") or 0),
                     "kind": e.get("kind", "event"),
                     "summary": e.get("summary") or e.get("message")
                                or e.get("name") or "?",
                     "source": e.get("source", "unknown"),
                     "target": e.get("target") or e.get("service"),
                     "raw_ref": e.get("id") or e.get("fact_id")})
    norm.sort(key=lambda e: e["at"])
    kinds = {}
    for e in norm:
        kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
    return {"timeline": norm, "counts": {"events": len(norm), **kinds}}


def postmortem(incident: dict[str, Any],
               hypotheses: list[dict[str, Any]] | None = None,
               facts: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Draft postmortem — evidence-only, gaps named as gaps."""
    hyps = hypotheses or incident.get("hypotheses") or []
    # root cause only when exactly one hypothesis is strongly-supported
    strong = [h for h in hyps if h.get("causality") == "strongly-supported"]
    contradicted = [h for h in hyps if h.get("causality") == "contradicted"]
    if len(strong) == 1 and not contradicted:
        root = {"status": "candidate-root-cause",
                "evidence": strong[0],
                "note": "strongly-supported ≠ confirmed — human sign-off "
                        "required"}
    else:
        root = {"status": "unresolved",
                "reason": ("multiple equally-supported hypotheses"
                           if len(strong) > 1 else
                           "contradiction present"
                           if contradicted else
                           "no hypothesis reached strongly-supported")}
    return {
        "postmortem": {
            "title": incident.get("title", "incident"),
            "status": "draft",
            "root_cause": root,
            "timeline_events": len(incident.get("timeline") or []),
            "hypotheses": [{"summary": (h.get("change") or h),
                            "causality": h.get("causality", "unknown")}
                           for h in hyps],
            "evidence_ids": [f.get("fact_id") for f in facts or []
                             if f.get("fact_id")],
            "open_questions": [
                "confirm root cause via independent evidence",
                "verify action items against observed state",
            ],
            "note": "draft generated from evidence only — a blank root "
                    "cause is a true state, not a template error"}}
