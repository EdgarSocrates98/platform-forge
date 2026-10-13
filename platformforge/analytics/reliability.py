"""Cycle 5 Phase H (2/2) — reliability intelligence (§115–124).

MTTR only from trusted timestamps (§118); change failure rate only
when deploy↔incident links exist (§119); centrality ≠ criticality —
reported as separate evidence (§122–124).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from platformforge.analytics.models import confidence_for_support
from platformforge.live.models import parse_ts


@dataclass
class ReliabilityProfile:
    """§116–117."""
    service_id: str
    slo: dict[str, Any] = field(default_factory=dict)
    error_budget_remaining: float | None = None
    incident_count: int = 0
    mttr_seconds: float | None = None
    change_failure_rate: float | None = None
    rollback_count: int = 0
    dependency_criticality: str = "unknown"
    redundancy: int | None = None
    capacity_risk: str = "unknown"
    confidence: str = "low"
    sample_size: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {"schema": "platformforge/reliability-profile/v1",
                **asdict(self)}


def build_profile(service_id: str,
                  incidents: list[dict[str, Any]],
                  changes: list[dict[str, Any]],
                  rollbacks: list[dict[str, Any]],
                  slo: dict[str, Any] | None = None) -> ReliabilityProfile:
    """Assemble a profile from linked events; each metric keeps its own
    evidence requirements."""
    p = ReliabilityProfile(service_id=service_id, slo=slo or {})
    p.incident_count = len(incidents)
    p.rollback_count = len(rollbacks)
    # §118 — MTTR only when incident open/resolve timestamps parse
    deltas = []
    for i in incidents:
        a, b = parse_ts(i.get("opened_at")), parse_ts(i.get("resolved_at"))
        if a and b and b >= a:
            deltas.append((b - a).total_seconds())
    if deltas:
        p.mttr_seconds = round(sum(deltas) / len(deltas), 1)
    # §119 — change failure rate only with deploy↔incident links
    linked = [c for c in changes if c.get("incident_linked")]
    if changes:
        p.change_failure_rate = round(len(linked) / len(changes), 3)
    p.sample_size = len(incidents) + len(changes)
    p.confidence = confidence_for_support(p.sample_size)
    return p


def fleet_hotspots(profiles: list[ReliabilityProfile],
                   min_sample: int = 3) -> list[dict[str, Any]]:
    """§120–121 — decomposed hotspot evidence."""
    out = []
    for p in profiles:
        reasons = []
        if p.incident_count >= min_sample:
            reasons.append(f"{p.incident_count} incidents")
        if p.rollback_count >= 2:
            reasons.append(f"{p.rollback_count} rollbacks")
        if p.change_failure_rate is not None and \
           p.change_failure_rate >= 0.3 and p.sample_size >= min_sample:
            reasons.append(f"change_failure_rate={p.change_failure_rate}")
        if p.error_budget_remaining is not None and \
           p.error_budget_remaining < 0.2:
            reasons.append("error budget nearly exhausted")
        if reasons:
            out.append({"service_id": p.service_id, "type":
                        "ReliabilityHotspot",
                        "evidence": reasons,
                        "confidence": p.confidence,
                        "sample_size": p.sample_size})
    return out


def blast_concentration(graph, top: int = 5) -> list[dict[str, Any]]:
    """§122–124 — high dependency centrality, reported *separately*
    from criticality. Centrality alone never marks a node critical."""
    deg: dict[str, int] = {}
    for e in graph.edges.values():
        if e.kind in ("depends_on", "calls", "consumes", "reads",
                      "writes"):
            deg[e.dst] = deg.get(e.dst, 0) + 1
    out = []
    for nid, d in sorted(deg.items(), key=lambda kv: -kv[1])[:top]:
        node = graph.nodes.get(nid)
        out.append({"node_id": nid, "in_degree": d,
                    "declared_criticality": (node.attrs.get("criticality")
                                             if node else None),
                    "note": "centrality ≠ criticality",
                    "confidence": "medium" if d >= 5 else "low"})
    return out
