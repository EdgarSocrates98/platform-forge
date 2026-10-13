"""Cycle 5 Phase N — fleet/analytics invariant probes (§286–292).

Deterministic functions returning {"ok": bool, "detail": ...}. Each
probe encodes one spec invariant that scripted lab scenarios can't
reach: unknown-handling, provenance, small-sample honesty, boundary
conditions (correlation≠causality, centrality≠criticality,
low-util≠deletable, uncertain optimization never auto-promoted).
"""

from __future__ import annotations

from typing import Any


def probe_partial_coverage_visible(tmp) -> dict[str, Any]:
    """§286 — a permission-limited member is still reported; coverage
    stays <1 and the member is never silently dropped."""
    from platformforge.fleet.models import FleetSnapshot, MemberObservation
    snap = FleetSnapshot(
        fleet_id="f",
        member_observations=[
            MemberObservation(member_id="cluster:a", status="observed",
                              coverage=1.0),
            MemberObservation(member_id="cluster:b",
                              status="permission-limited",
                              coverage=0.3)])
    d = snap.to_dict()
    ok = snap.coverage < 1.0 and \
        any(o.member_id == "cluster:b"
            for o in snap.member_observations) and \
        d.get("coverage") is not None
    return {"ok": ok, "detail": f"coverage={snap.coverage}"}


def probe_small_sample_confidence(tmp) -> dict[str, Any]:
    """§288 — small samples never produce high confidence; the engine
    reports insufficient-history below the minimum support."""
    from datetime import datetime, timezone

    from platformforge.analytics.history import HistoryEngine
    eng = HistoryEngine()
    eng.ingest_events("incident", [
        {"ts": datetime.now(timezone.utc).isoformat(),
         "subject": "svc:s1", "type": "incident"}], "t")
    pats = eng.patterns("90d")
    ok = not pats or all(p.confidence != "high" for p in pats)
    # a single event must never reach `high`
    return {"ok": ok,
            "detail": f"patterns={len(pats)} "
                      f"conf={[p.confidence for p in pats]}"}


def probe_absent_allocation_unknown(tmp) -> dict[str, Any]:
    """§289 — cost with no allocation data reports unallocated/unknown,
    never a fabricated zero."""
    from platformforge.analytics.finops_v4 import cost_hierarchy
    h = cost_hierarchy([])
    ok = h.get("total", -1) == 0 or "unallocated" in h
    # a doc with amounts but no allocation keys keeps them visible
    h2 = cost_hierarchy([{"amount": 500}])
    ok = ok and h2.get("unallocated", 0) >= 1
    return {"ok": ok, "detail": h2}


def probe_centrality_not_criticality(tmp) -> dict[str, Any]:
    """§290 — blast concentration never *assigns* criticality; a
    high-centrality node without declared criticality stays None and
    the entry carries the explicit disclaimer."""
    from platformforge.analytics.reliability import blast_concentration
    from platformforge.graph.model import Edge, Graph, Node
    g = Graph()
    for n in ("a", "b", "c", "d"):
        g.add_node(Node.make("service", n))
    for s, d in (("a", "b"), ("a", "c"), ("a", "d")):
        g.add_edge(Edge(f"service/{s}", f"service/{d}", "depends_on"))
    conc = blast_concentration(g)
    top = conc[0] if conc else {}
    ok = bool(conc) and top.get("declared_criticality") is None and \
        "criticality" in top.get("note", "") and \
        all("in_degree" in e for e in conc)
    return {"ok": ok, "detail": conc}


def probe_low_util_not_deletable(tmp) -> dict[str, Any]:
    """§290 — idle/underused resources are never marked deletable."""
    from platformforge.analytics.finops_v4 import idle_resources
    idle = idle_resources([
        {"id": "vm:1", "requests_30d": 0, "cpu_util": 1,
         "attached": True, "cost_monthly": 100},
        {"id": "vol:2", "orphaned": True, "attached": False,
         "cpu_util": 0, "cost_monthly": 50}])
    ok = bool(idle) and not any(i.get("deletable") for i in idle)
    return {"ok": ok, "detail": idle}


def probe_correlation_not_causality(tmp) -> dict[str, Any]:
    """§291 — repeated co-occurrence produces a hypothesis with
    limitations, never a causal claim."""
    from datetime import datetime, timedelta, timezone

    from platformforge.analytics.history import HistoryEngine
    eng = HistoryEngine()
    now = datetime.now(timezone.utc)
    evs = [{"ts": (now - timedelta(days=i)).isoformat(),
            "subject": "svc:s", "type": "incident"}
           for i in range(1, 6)]
    eng.ingest_events("incident", evs, "t")
    pats = eng.patterns("90d")
    d = pats[0].to_dict() if pats else {}
    ok = bool(pats) and not d.get("causal_claim", True) and \
        bool(d.get("limitations"))
    return {"ok": ok, "detail": d}


def probe_uncertain_optimization_suppressed(tmp) -> dict[str, Any]:
    """§292 — high-uncertainty opportunities never promote to recs."""
    from platformforge.optimize.engine import OptimizationEngine
    from platformforge.optimize.models import OptimizationOpportunity
    eng = OptimizationEngine()
    eng.add_opportunity(OptimizationOpportunity(
        opportunity_id="o1", type="cost", scope={"svc": "s"},
        evidence=[], uncertainty="high"))
    eng.add_opportunity(OptimizationOpportunity(
        opportunity_id="o2", type="cost", scope={"svc": "s2"},
        evidence=[{"fact_id": "f1"}], uncertainty="low"))
    recs = eng.recommendations()
    ok = len(recs) == 1 and recs[0].recommendation_id.endswith("o2")
    return {"ok": ok, "detail": [r.recommendation_id for r in recs]}


def probe_plan_changeintent_only(tmp) -> dict[str, Any]:
    """§303 — plan() returns a ChangeIntent; no path to envelope."""
    from platformforge.ops.models import ChangeIntent
    from platformforge.optimize.engine import OptimizationEngine
    from platformforge.optimize.models import OptimizationRecommendation
    rec = OptimizationRecommendation(
        recommendation_id="r1", type="cost", scope={"svc": "s"},
        confidence="low")
    ci = OptimizationEngine.plan(rec)
    ok = isinstance(ci, ChangeIntent) and \
        ci.reason.type == "recommendation"
    return {"ok": ok, "detail": ci.reason.type}


def probe_missing_denominator(tmp) -> dict[str, Any]:
    """§195/§361 — cost/token is absent without an observed token
    count; the metric is never fabricated."""
    from platformforge.aiplat.models import ai_unit_economics
    ue = ai_unit_economics(9800, tokens=None)
    ok = "cost_per_1m_tokens" not in ue and ue.get("cost") == 9800
    return {"ok": ok, "detail": ue}


def probe_federation_secret_denied(tmp) -> dict[str, Any]:
    """§302 — export_summary denies any payload containing a secret,
    regardless of classification."""
    from platformforge.federation.node import NodeManifest, export_summary
    node = NodeManifest(node_id="n", capabilities=["fleet"])
    for cls in ("public", "internal"):
        s = export_summary(node, {"api_key": "AKIAIOSFODNN7EXAMPLE"},
                           cls)
        if s.get("action") != "deny":
            return {"ok": False, "detail": f"{cls} leaked: {s}"}
    return {"ok": True, "detail": "secrets denied at all tiers"}


def probe_federation_restricted_denied(tmp) -> dict[str, Any]:
    """§302 — restricted classification is denied by default."""
    from platformforge.federation.node import NodeManifest, export_summary
    node = NodeManifest(node_id="n", capabilities=["fleet"])
    s = export_summary(node, {"details": "pii-ish"}, "restricted")
    return {"ok": s.get("action") == "deny", "detail": s}


def probe_member_key_deterministic(tmp) -> dict[str, Any]:
    """§296 — fleet member identity is deterministic across runs."""
    from platformforge.fleet.models import member_key
    a = member_key("cluster", "prod-1")
    b = member_key("cluster", "prod-1")
    c = member_key("cluster", "prod-2")
    return {"ok": a == b and a != c, "detail": a}


def probe_dx_no_person_metrics(tmp) -> dict[str, Any]:
    """§287 — DX metrics never carry per-person/individual fields."""
    from platformforge.analytics.dx import dx_metrics, guard_no_person_metrics
    m = dx_metrics([
        {"path": "web", "requested_at": "2025-11-01T09:00:00Z",
         "ready_at": "2025-11-01T09:30:00Z", "status": "provisioned",
         "approval_wait_s": 300},
        {"path": "web", "requested_at": "2025-11-02T09:00:00Z",
         "ready_at": "2025-11-02T09:20:00Z", "status": "provisioned"}])
    bad = guard_no_person_metrics(m)
    return {"ok": not bad and m.get("scope", "").startswith("team"),
            "detail": f"violations={bad}"}


def probe_history_window_deterministic(tmp) -> dict[str, Any]:
    """§298 — identical events + window → identical patterns."""
    from datetime import datetime, timedelta, timezone

    from platformforge.analytics.history import HistoryEngine
    now = datetime.now(timezone.utc)
    evs = [{"ts": (now - timedelta(days=i)).isoformat(),
            "subject": "svc:s", "type": "incident"}
           for i in range(1, 4)]
    outs = []
    for _ in range(2):
        eng = HistoryEngine()
        eng.ingest_events("incident", evs, "t")
        outs.append([p.to_dict() for p in eng.patterns("90d")])
    return {"ok": outs[0] == outs[1],
            "detail": f"runs_equal={outs[0] == outs[1]}"}


PROBES = {
    "partial-coverage-visible": probe_partial_coverage_visible,
    "small-sample-confidence": probe_small_sample_confidence,
    "absent-allocation-unknown": probe_absent_allocation_unknown,
    "centrality-not-criticality": probe_centrality_not_criticality,
    "low-util-not-deletable": probe_low_util_not_deletable,
    "correlation-not-causality": probe_correlation_not_causality,
    "uncertain-optimization-suppressed":
        probe_uncertain_optimization_suppressed,
    "plan-changeintent-only": probe_plan_changeintent_only,
    "missing-denominator": probe_missing_denominator,
    "federation-secret-denied": probe_federation_secret_denied,
    "federation-restricted-denied": probe_federation_restricted_denied,
    "member-key-deterministic": probe_member_key_deterministic,
    "dx-no-person-metrics": probe_dx_no_person_metrics,
    "history-window-deterministic": probe_history_window_deterministic,
}


def probe_fleet_report_all_cited(tmp) -> dict[str, Any]:
    """Every invest_next entry in a fleet report must carry evidence;
    suppressed opportunities stay visible; coverage bounds the verdict."""
    import argparse
    import tempfile
    from pathlib import Path

    from platformforge.cli.fleetcmd import cmd_fleet
    src = Path("lab/fleets/acme")
    with tempfile.TemporaryDirectory() as td:
        for f in src.glob("*.yaml"):
            (Path(td) / f.name).write_text(f.read_text())
        ns = argparse.Namespace(fleet_cmd="report", path=td, question="",
                                window="", limit=5, id="", out="",
                                format="json")
        r = cmd_fleet(ns)
    inv = r.get("invest_next", [])
    cited = all(i.get("evidence") for i in inv)
    return {"ok": bool(inv) and cited
            and r.get("portfolio", {}).get("suppressed", 0) > 0
            and r.get("coverage", {}).get("min_member", 1) < 1,
            "detail": {"invest": len(inv), "all_cited": cited,
                       "suppressed": r.get("portfolio", {}).get("suppressed")}}


PROBES["fleet-report-all-cited"] = probe_fleet_report_all_cited
