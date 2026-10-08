"""Cycle 5 §204–205 — opportunity generation from analytics signals.

`scan_fleet(data, graph)` feeds every analytics output into the
OptimizationEngine as evidence-cited opportunities. Uncertainty is
honest: a signal becomes `medium` only when its underlying measure
was *observed* with enough support; otherwise it stays `high` and
is suppressed from recommendations — visible in
`portfolio().suppressed`, never silently dropped.
"""

from __future__ import annotations

from typing import Any

from platformforge.analytics.capacity import (
    CapacityDimension,
    CapacitySnapshot,
    capacity_risk,
)
from platformforge.analytics.finops_v4 import (
    cost_hierarchy,
    idle_resources,
    rightsizing,
)
from platformforge.analytics.goldenpath import golden_path_analytics
from platformforge.analytics.opsanalytics import (
    operation_hotspots,
    remediation_recurrence,
)
from platformforge.analytics.policyintel import (
    false_positive_candidates,
    policy_metrics,
)
from platformforge.analytics.reliability import build_profile, fleet_hotspots
from platformforge.fleet.query import FLEET_QUESTIONS, fleet_query
from platformforge.optimize.engine import OptimizationEngine
from platformforge.optimize.models import OptimizationOpportunity

_RISK_QUESTIONS = {
    "public-services": "security",
    "wildcard-iam": "security",
    "unsupported-k8s": "standardization",
    "unowned": "standardization",
    "no-slo": "reliability",
    "outside-golden-path": "platform-product",
    "idle-high-cost": "cost",
    "cross-env-deps": "reliability",
}


def capacity_snapshots(capacity: dict[str, Any]) -> dict[str, CapacitySnapshot]:
    """capacity.yaml `members:` → member_id → CapacitySnapshot."""
    return {
        m["member_id"]: CapacitySnapshot(
            member_id=m["member_id"],
            dimensions=[CapacityDimension(
                d["name"], d.get("used"), d.get("capacity"),
                d.get("source", "observed"))
                for d in m.get("dimensions", [])])
        for m in capacity.get("members", [])}


def scan_fleet(data: dict[str, Any], graph=None,
               engine: OptimizationEngine | None = None,
               coverage: float | None = None) -> OptimizationEngine:
    """Generate opportunities from a loaded fleet bundle (same file
    shapes as lab fixtures — see `fleet.loader.FLEET_FILES`)."""
    eng = engine or OptimizationEngine()
    n = [0]

    def add(type_: str, scope: dict, evidence: list, uncertainty: str,
            savings=None, unit="", refs=None) -> None:
        n[0] += 1
        eng.add_opportunity(OptimizationOpportunity(
            opportunity_id=f"scan-{n[0]}",
            type=type_, scope=scope, evidence=evidence,
            pattern_refs=refs or [], estimated_savings=savings,
            savings_unit=unit, uncertainty=uncertainty,
            coverage=coverage))

    costs = data.get("costs") or {}

    # --- cost signals (§100–101: idle ≠ deletable — always review) ---
    raw_res = {r.get("id"): r for r in costs.get("resources", [])}
    for r in idle_resources(costs.get("resources", [])):
        res = raw_res.get(r["resource"], {})
        add("cost", {"resource": str(r["resource"])},
            [f"idle:{r['resource']}",
             *[f"{k}:{v}" for k, v in r["evidence"].items()]],
            "medium" if len(r["evidence"]) >= 3 else "high",
            savings=res.get("cost_monthly"), unit="cost_monthly")
    for w in costs.get("workloads", []):
        rs = rightsizing(w)
        if rs:
            add("cost", {"workload": str(rs["workload"])},
                [f"rightsizing:{rs['workload']}:{rs['type']}",
                 *[f"{k}:{v}" for k, v in rs["evidence"].items()]],
                "medium" if rs["signals_used"] >= 3 else "high",
                savings=w.get("cost_monthly"), unit="cost_monthly")
    tree = cost_hierarchy(costs.get("allocations", []))
    if tree["unallocated"]:
        add("cost", {"fleet": "unallocated"},
            [f"unallocated:{tree['unallocated']}",
             f"unallocated_ratio:{tree['unallocated_ratio']}"],
            "medium", savings=tree["unallocated"], unit="cost_monthly",
            refs=["cost allocation coverage gap"])
    by_svc = tree["by_level"].get("service", {})
    if by_svc:
        svc, d = max(by_svc.items(), key=lambda kv: kv[1]["amount"])
        add("cost", {"service": svc},
            [f"top-cost:{svc}={d['amount']}",
             f"alloc-confidence:{d['confidence']}"], "medium")

    # --- capacity ------------------------------------------------------
    cap = data.get("capacity") or {}
    meta = {m["member_id"]: m for m in cap.get("members", [])}
    for mid, snap in capacity_snapshots(cap).items():
        m = meta.get(mid, {})
        risk = capacity_risk(
            snap, criticality=m.get("criticality"),
            autoscaling=m.get("autoscaling"),
            failure_domains=m.get("failure_domains"))
        if risk["risk"] == "high":
            add("capacity", {"member": mid},
                [f"saturated:{','.join(risk['factors']['saturated_dimensions'])}",
                 f"criticality:{risk['factors']['criticality']}",
                 f"failure_domains:{risk['factors']['failure_domains']}"],
                "medium" if risk["confidence"] == "medium" else "high")

    # --- reliability / operations --------------------------------------
    ev = data.get("events") or {}
    incidents = ev.get("incident", [])
    deployments = ev.get("deployment", [])
    rollbacks = ev.get("rollback", [])
    services = sorted({i.get("service") for i in incidents
                       if i.get("service")})
    profiles = [build_profile(
        s,
        [i for i in incidents if i.get("service") == s],
        [c for c in deployments if c.get("service") == s],
        [r for r in rollbacks if r.get("service") == s])
        for s in services]
    for h in fleet_hotspots(profiles):
        add("reliability", {"service": h["service_id"]},
            [f"hotspot:{h['service_id']}",
             *[f"ev:{e}" for e in h["evidence"]]],
            "medium" if h["sample_size"] >= 5 else "high")
    for h in operation_hotspots(ev.get("operation", [])):
        add("operational",
            {"service": h["service"], "action": h["action"]},
            [f"repeated-operation:{h['action']}x{h['count']}"],
            "medium" if h["count"] >= 4 else "high")
    for r in remediation_recurrence(ev.get("remediation", [])):
        add("operational", {"finding": r["finding"]},
            [f"recurrence:{r['finding']}x{r['recurrences']}",
             f"path:{r['suggested_path']}",
             *[f"ref:{e}" for e in r["evidence"]]],
            "medium" if r["recurrences"] >= 3 else "high")

    # --- policies (review-only; never auto-applied) ----------------------
    pol = data.get("policies") or {}
    m = policy_metrics(pol.get("decisions", []),
                       exceptions=pol.get("exceptions", []),
                       overrides=pol.get("overrides", []))
    for fp in false_positive_candidates(m, pol.get("outcomes", {})):
        add("platform-product", {"policy": fp["policy"]},
            [f"false-positive-candidate:{fp['policy']}",
             *[f"{k}:{v}" for k, v in fp.items() if isinstance(v, (int, float))]],
            "medium", refs=["policy review — humans change policy"])

    # --- golden path -----------------------------------------------------
    req = data.get("requests") or {}
    gp = golden_path_analytics(req.get("requests", []),
                               outcomes=req.get("outcomes", []),
                               escapes=req.get("escapes", []))
    for pid, pa in gp.get("paths", {}).items():
        esc = pa.get("escape_reasons", {})
        if esc:
            reason, cnt = max(esc.items(), key=lambda kv: kv[1])
            add("platform-product", {"golden_path": pid},
                [f"escapes:{pid}:{reason}={cnt}",
                 f"success_rate:{pa.get('success_rate')}"],
                "medium" if sum(esc.values()) >= 2 else "high")

    # --- graph questions ---------------------------------------------------
    if graph is not None:
        for q, type_ in _RISK_QUESTIONS.items():
            if q not in FLEET_QUESTIONS:
                continue
            for it in fleet_query(graph, q).get("items", []):
                node = it.get("node_id", "?")
                fact_ids = it.get("fact_ids") or []
                add(type_, {"node": node},
                    [f"{q}:{node}", *[f"fact:{fi}" for fi in fact_ids]],
                    "medium" if fact_ids else "high")
    return eng
