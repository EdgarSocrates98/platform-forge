"""Incident intelligence V3 (cycle §160–§176).

Canonical timeline joins: git change, CI build, artifact, deployment,
CloudTrail change, k8s event, runtime anomaly, alert, incident — every
event normalized to {timestamp, source, scope, resources, actor, facts,
confidence, kind}.

Candidate scoring is deterministic and factorized — every hypothesis
explains WHERE its rank came from (§170). Status vocabulary is closed:
confirmed needs causal evidence — correlation alone is never enough;
`root_cause: unresolved` is a valid, honest outcome (§174).
"""

from __future__ import annotations

from typing import Any

from platformforge.live.models import parse_ts

EVENT_SOURCES = ("git_change", "ci_build", "artifact", "deployment",
                 "cloudtrail", "k8s_event", "runtime_anomaly", "alert",
                 "incident", "manual")

# §170 — fixed factor weights; every candidate's score is reproducible
# and explainable from this table.
WEIGHTS = {"temporal": 0.25, "graph_distance": 0.15,
           "blast_radius": 0.10, "scope_overlap": 0.10,
           "change_type": 0.10, "freshness": 0.10,
           "evidence_tier": 0.10, "runtime_correlation": 0.10}

MUTATING_ACTION_HINTS = ("create", "update", "put", "delete", "apply",
                         "deploy", "scale", "patch", "modify",
                         "attach", "detach")

HYPOTHESIS_STATUSES = ("confirmed", "supported", "candidate",
                       "contradicted", "unknown")


def _ts(e: dict[str, Any]) -> float:
    v = e.get("timestamp") or e.get("at") or e.get("ts") or ""
    t = parse_ts(str(v))
    return t.timestamp() if t else float(v) if str(v).replace(
        ".", "", 1).isdigit() else 0.0


def normalize_event(raw: dict[str, Any]) -> dict[str, Any]:
    """Any event source → canonical timeline event; scoring-relevant
    extras (blast_radius, runtime_correlated, …) pass through."""
    e = dict(raw)
    e.update({
        "timestamp": raw.get("timestamp") or raw.get("at") or "",
        "at": _ts(raw),
        "kind": raw.get("kind") or raw.get("source") or "event",
        "source": raw.get("source", "unknown"),
        "scope": raw.get("scope") or {
            k: raw.get(k) for k in ("cluster", "namespace", "account",
                                    "region") if raw.get(k)},
        "resources": raw.get("resources") or raw.get("resource_ids") or
        ([raw.get("target")] if raw.get("target") else []),
        "actor": raw.get("actor") or raw.get("user") or "",
        "facts": raw.get("facts") or raw.get("fact_ids") or [],
        "confidence": float(raw.get("confidence", 0.8)),
        "summary": raw.get("summary") or raw.get("action")
        or raw.get("message") or "",
        "tier": raw.get("tier"), "freshness": raw.get("freshness", ""),
        "causal": bool(raw.get("causal"))})
    return e


def build_timeline(events: list[dict[str, Any]]) -> dict[str, Any]:
    norm = sorted((normalize_event(e) for e in events),
                  key=lambda e: (e["at"], e["kind"]))
    by_source: dict[str, int] = {}
    for e in norm:
        by_source[e["kind"]] = by_source.get(e["kind"], 0) + 1
    return {"timeline": norm, "counts": {"events": len(norm),
                                          **by_source}}


def _factor_scores(candidate: dict[str, Any], incident_at: float,
                   incident_resources: set[str],
                   window_s: float, graph=None) -> dict[str, float]:
    dt = incident_at - _ts(candidate)
    temporal = max(0.0, 1 - abs(dt) / window_s) if dt >= 0 else 0.0
    c_res = set(candidate.get("resources") or
                candidate.get("resource_ids") or [])
    overlap = len(incident_resources & c_res) / \
        max(1, len(incident_resources | c_res)) \
        if incident_resources or c_res else 0.0
    action = str(candidate.get("action") or candidate.get("kind") or "")
    change_type = 1.0 if any(h in action.lower()
                             for h in MUTATING_ACTION_HINTS) else 0.3
    fresh = {"fresh": 1.0, "aging": 0.6, "stale": 0.3,
             "expired": 0.1}.get(candidate.get("freshness", ""), 0.5)
    tier = candidate.get("tier")
    tier_score = {0: 1.0, 1: 0.9, 2: 0.7, 3: 0.5,
                  4: 0.4, 5: 0.3}.get(tier, 0.5)
    gd = 0.0
    if graph is not None and incident_resources and c_res:
        from platformforge.graph.query import blast_radius
        for r in c_res:
            if r in incident_resources:
                gd = 1.0
                break
            try:
                br = blast_radius(graph, r)["nodes"]
            except (KeyError, TypeError, ValueError):
                br = {}
            for ir in incident_resources:
                if ir in br:
                    gd = max(gd, max(0.0, 1 - 0.2 * br[ir]["depth"]))
    blast = min(1.0, float(candidate.get("blast_radius", 0.0)))
    runtime = 1.0 if candidate.get("runtime_correlated") else 0.0
    return {"temporal": round(temporal, 3), "graph_distance": round(gd, 3),
            "blast_radius": blast, "scope_overlap": round(overlap, 3),
            "change_type": change_type, "freshness": fresh,
            "evidence_tier": tier_score, "runtime_correlation": runtime}


def score_candidates(incident: dict[str, Any],
                     candidates: list[dict[str, Any]],
                     *, window_s: float = 3600,
                     graph=None) -> dict[str, Any]:
    """Deterministic ranked hypotheses with per-factor explanation."""
    incident_at = _ts(incident)
    res = set(incident.get("resources") or
              incident.get("resource_ids") or [])
    ranked = []
    for c in candidates:
        c = normalize_event(c) if "timestamp" in c or "at" in c else c
        factors = _factor_scores(c, incident_at, res, window_s, graph)
        score = round(sum(WEIGHTS[k] * factors[k] for k in WEIGHTS), 3)
        dt = incident_at - _ts(c)
        if c.get("contradicted") or dt < 0:
            status = "contradicted"   # change after incident ≠ cause
        elif c.get("causal") and c.get("facts"):
            status = "confirmed"      # causal evidence present
        elif score >= 0.65:
            status = "supported"
        elif score >= 0.3:
            status = "candidate"
        else:
            status = "unknown"
        ranked.append({"candidate": c.get("summary") or
                       c.get("action") or c.get("kind", "?"),
                       "resources": sorted(c.get("resources") or
                                           c.get("resource_ids") or []),
                       "actor": c.get("actor", ""),
                       "timestamp": c.get("timestamp") or c.get("at"),
                       "score": score, "status": status,
                       "explain": {"factors": factors,
                                   "weights": WEIGHTS,
                                   "dt_seconds": round(dt, 1)}})
    ranked.sort(key=lambda r: (-r["score"], r["candidate"]))
    for i, r in enumerate(ranked):
        r["rank"] = i + 1
    return {"ranked": ranked,
            "statuses": {s: sum(1 for r in ranked if r["status"] == s)
                         for s in HYPOTHESIS_STATUSES},
            "note": "correlation ≠ causation — 'confirmed' requires "
                    "causal evidence, rank explains score only"}


def postmortem_v3(incident: dict[str, Any],
                  timeline: dict[str, Any],
                  ranked: dict[str, Any]) -> dict[str, Any]:
    """§174 — evidence-only postmortem draft. Root cause stays
    `unresolved` unless a confirmed hypothesis exists (causal evidence,
    not correlation)."""
    hyps = ranked.get("ranked", [])
    confirmed = [h for h in hyps if h["status"] == "confirmed"]
    supported = [h for h in hyps if h["status"] == "supported"]
    root = ({"status": "confirmed-candidate",
             "evidence": confirmed[0],
             "note": "causal evidence present — still requires human "
                     "sign-off"} if len(confirmed) == 1 else
            {"status": "unresolved",
             "reason": ("multiple confirmed candidates" if confirmed else
                        "no causal evidence — correlation only")})
    unknowns = [h["candidate"] for h in hyps if h["status"] == "unknown"]
    return {"postmortem": {
        "title": incident.get("title", "incident"),
        "incident_id": incident.get("incident_id", ""),
        "status": "draft",
        "timeline": timeline.get("timeline", []),
        "impact": incident.get("impact", {}),
        "observed_changes": confirmed + supported,
        "runtime_signals": [e for e in timeline.get("timeline", [])
                            if e["kind"] in ("runtime_anomaly",
                                             "alert")],
        "candidate_causes": hyps,
        "root_cause": root,
        "unknowns": unknowns,
        "follow_ups": [
            "confirm or reject top hypothesis with independent evidence",
            ("verify declared state vs observed drift for affected "
             "resources"),
            "add regression coverage for the failing invariant"],
        "note": "draft generated from evidence only — 'unresolved' is "
                "a true state, not a template gap"}}
