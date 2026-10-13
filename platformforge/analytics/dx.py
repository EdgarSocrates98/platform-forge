"""Cycle 5 — developer experience intelligence (§142–149).

Measures *platform friction* at team level — never individual
productivity (§144–145, §305). Individual names are never required
and never surfaced (§149); aggregation is the default (§148).
"""

from __future__ import annotations

from typing import Any

# hard guard — fields that would turn this into surveillance
FORBIDDEN_METRICS = ("per_person", "individual", "developer_score",
                     "productivity_score", "person_id")


def dx_metrics(events: list[dict[str, Any]]) -> dict[str, Any]:
    """§147 — team/platform-level friction metrics only."""
    prov, failed, approvals, manual, retries, escapes = 0, 0, 0, 0, 0, 0
    waits = []
    for e in events:
        t = e.get("type")
        if t == "provision":
            prov += 1
            if e.get("wait_s"):
                waits.append(e["wait_s"])
        elif t == "request-failed":
            failed += 1
        elif t == "approval-required":
            approvals += 1
            if e.get("wait_s"):
                waits.append(e["wait_s"])
        elif t == "manual-handoff":
            manual += 1
        elif t == "retry":
            retries += 1
        elif t == "escape":
            escapes += 1
    total = prov + failed
    waits.sort()
    return {"schema": "platformforge/dx-metrics/v1",
            "median_provision_wait_s": waits[len(waits) // 2]
            if waits else "unknown",
            "failed_request_rate": round(failed / total, 3)
            if total else "unknown",
            "manual_intervention_rate":
            round(manual / max(total, 1), 3),
            "approval_events": approvals, "retry_events": retries,
            "escape_events": escapes,
            "scope": "team/platform — no individual metrics",
            "sample_size": len(events)}


def guard_no_person_metrics(metrics: dict[str, Any]) -> list[str]:
    """§305 property — scan a metric dict for surveillance-shaped keys."""
    bad = []

    def walk(o: Any, path: str = ""):
        if isinstance(o, dict):
            for k, v in o.items():
                kl = str(k).lower()
                if any(f in kl for f in FORBIDDEN_METRICS):
                    bad.append(f"{path}.{k}" if path else str(k))
                walk(v, f"{path}.{k}" if path else str(k))
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f"{path}[{i}]")
    walk(metrics)
    return bad
