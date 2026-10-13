"""Cycle 5 phases C–M — history, measurement, golden path, policy,
finops v4, capacity, reliability, optimize, federation, AI, economy."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from platformforge.aiplat.models import GPUCapacity, ai_capacity_risk, ai_unit_economics, detect_ai_workloads
from platformforge.analytics.capacity import CapacityDimension, CapacitySnapshot, capacity_risk, forecast
from platformforge.analytics.dx import dx_metrics, guard_no_person_metrics
from platformforge.analytics.finops_v4 import (
    anomalies,
    cost_hierarchy,
    cost_trend,
    idle_resources,
    rightsizing,
    unit_economics,
)
from platformforge.analytics.goldenpath import golden_path_analytics, golden_path_recommendations
from platformforge.analytics.history import engine_from_events
from platformforge.analytics.measurement import maturity_assessment, scorecard, self_service_ratio
from platformforge.analytics.models import AnalyticsDataQuality
from platformforge.analytics.policyintel import (
    false_positive_candidates,
    policy_drift,
    policy_metrics,
    policy_recommendations,
)
from platformforge.analytics.reliability import blast_concentration, build_profile
from platformforge.economy.fleetpack import drill_down, fleet_context_pack
from platformforge.federation.node import NodeManifest, export_summary, federated_query
from platformforge.graph.model import Edge, Graph, Node
from platformforge.optimize.engine import OptimizationEngine
from platformforge.optimize.models import OptimizationOpportunity

NOW = datetime.now(timezone.utc)
def _ts(days_ago: float) -> str:
    return (NOW - timedelta(days=days_ago)).isoformat()


# ---- Phase C: history -------------------------------------------------

def test_history_windows_and_support():
    evs = [{"ts": _ts(d), "subject": "svc-a", "outcome": "failed"}
           for d in (1, 3, 5)] + [{"ts": _ts(40), "subject": "svc-a",
                                   "outcome": "ok"}]
    eng = engine_from_events(evs, "operation")
    assert len(eng.events("7d")) == 3           # §299 — window excludes
    assert len(eng.events("90d")) == 4
    pats = eng.patterns("90d")
    assert pats and pats[0].confidence in ("low", "medium")
    assert pats[0].to_dict()["causal_claim"] is False  # §41


def test_history_before_and_stats():
    evs = [{"ts": _ts(d), "subject": "x", "type": "deploy"}
           for d in (2, 5, 9)] + \
          [{"ts": _ts(d - 0.5), "subject": "x", "type": "incident"}
           for d in (2, 5, 9)]
    eng = engine_from_events(evs[:3], "deployment")
    eng.ingest_events("incident", evs[3:], "test")
    pats = eng.before("incident", "24h", "90d")
    assert pats and pats[0].support >= 1


# ---- Phase D: measurement --------------------------------------------

def test_metric_unknown_never_zero():
    m = self_service_ratio(None, None)
    assert m.to_dict()["value"] == "unknown"     # §64/§304
    m2 = self_service_ratio(8, 10)
    assert m2.value == 0.8


def test_maturity_diagnostic_not_score():
    r = maturity_assessment({"adoption": {"observed": ["a", "b", "c"]}})
    assert r["dimensions"][1]["level"] == "defined"
    assert "unknown_dimensions" in r
    sc = scorecard({"reliability": "strong", "cost": "bogus"})
    assert sc["dimensions"]["cost"] == "unknown"
    assert sc["collapsed_score"] is None


# ---- Phase E: golden path ---------------------------------------------

def test_golden_path_analytics_and_recs():
    reqs = [{"path": "b", "status": "failed"}] * 4 + \
           [{"path": "a", "status": "provisioned"}] * 9 + \
           [{"path": "a", "status": "failed"}]
    esc = [{"path": "b", "reason": "policy-block"}] * 4
    a = golden_path_analytics(reqs, escapes=esc)
    assert a["paths"]["b"]["escape_reasons"]["policy-block"] == 4
    recs = golden_path_recommendations(a)
    assert recs and all(r["executes"] is False for r in recs)
    assert recs[0]["type"] in ("improve-golden-path", "reduce-friction")


# ---- Phase F: policy intel --------------------------------------------

def test_policy_metrics_false_positive_and_drift():
    dec = [{"policy": "p1", "decision": "deny"}] * 40 + \
          [{"policy": "p2", "decision": "shadow-deny"}] * 5
    exc = [{"policy": "p1"}] * 5
    m = policy_metrics(dec, exceptions=exc)
    assert m["p1"]["denies"] == 40 and m["p1"]["exceptions"] == 5
    fp = false_positive_candidates(m, {"p1": 4})
    assert fp[0]["verdict"] == "review-required"     # §53
    recs = policy_recommendations(m, fp)
    assert all(r["executes"] is False for r in recs)
    d = policy_drift(["p1", "p3"], ["p1", "p2"])
    assert d["drift"] and "p3" in d["configured_not_evaluated"]


# ---- Phase G: finops v4 -----------------------------------------------

def test_cost_hierarchy_unallocated_first_class():
    t = cost_hierarchy([
        {"team": "pay", "amount": 100, "allocation_confidence": "direct"},
        {"amount": 50, "unallocated": True}])
    assert t["unallocated"] == 50.0
    assert t["by_level"]["team"]["pay"]["amount"] == 100
    assert abs(t["unallocated_ratio"] - 1 / 3) < 0.01


def test_unit_economics_requires_denominator():
    assert unit_economics(100, None, "request")["value"] == "unknown"
    assert unit_economics(100, 200, "request")["value"] == 0.5


def test_rightsizing_needs_two_signals_and_idle_not_deletable():
    assert rightsizing({"id": "w", "cpu_util": 5}) is None      # §96
    r = rightsizing({"id": "w", "cpu_util": 5, "memory_util": 10,
                     "slo_headroom": 0.8, "requests": {"cpu": 4}})
    assert r["type"] == "downsize" and r["auto_apply"] is False
    idle = idle_resources([{"id": "vm", "requests_30d": 0,
                            "cpu_util": 1, "attached": True}])
    assert idle and idle[0]["deletable"] is False              # §101


def test_cost_trend_and_anomaly_deterministic():
    pts = [{"amount": 10 + i, "ts": f"d{i}"} for i in range(10)]
    t = cost_trend(pts)
    assert t["trend"] == "up" and t["method"]
    assert cost_trend(pts[:2])["trend"] == "insufficient-history"
    spikes = [{"amount": 10}] * 9 + [{"amount": 100, "ts": "x"}]
    assert anomalies(spikes)


# ---- Phase H: capacity + reliability ----------------------------------

def test_capacity_snapshot_and_forecast():
    snap = CapacitySnapshot(member_id="c1", dimensions=[
        CapacityDimension("cpu", used=9.0, capacity=10.0),
        CapacityDimension("gpu", used=None, capacity=8.0)])
    s = snap.saturation()
    assert "cpu" in s["saturated_dimensions"]
    assert "gpu" in s["unknown_dimensions"]
    f = forecast([{"used": i} for i in range(5)])
    assert f["level"] == "trend" and f["confidence"] == "low"
    assert forecast([{"used": 1}])["level"] == "insufficient-history"
    risk = capacity_risk(snap, criticality="critical")
    assert risk["risk"] == "high"


def test_reliability_profile_and_centrality():
    inc = [{"opened_at": _ts(3), "resolved_at": _ts(2.9)},
           {"opened_at": _ts(2), "resolved_at": _ts(1.9)}]
    ch = [{"id": "c1", "incident_linked": True}, {"id": "c2"}]
    p = build_profile("svc-a", inc, ch, [{"id": "r1"}])
    assert p.mttr_seconds and p.change_failure_rate == 0.5
    g = Graph()
    for i in range(6):
        g.add_node(Node.make("service", f"s{i}"))
        g.add_node(Node.make("database", "db"))
        g.add_edge(Edge(f"service/s{i}", "database/db", "depends_on"))
    conc = blast_concentration(g)
    assert conc[0]["node_id"] == "database/db"
    assert "centrality ≠ criticality" in conc[0]["note"]   # §123


# ---- Phase I: optimize -------------------------------------------------

def test_optimization_boundary_and_priority():
    dq = AnalyticsDataQuality(coverage=1.0, completeness=1.0,
                              sample_size=20)
    eng = OptimizationEngine(dq)
    eng.add_opportunity(OptimizationOpportunity(
        opportunity_id="o1", type="cost", scope={"w": "svc-a"},
        evidence=["e1"], estimated_savings=500, uncertainty="low"))
    eng.add_opportunity(OptimizationOpportunity(
        opportunity_id="o2", type="cost", scope={"w": "svc-b"},
        evidence=[], uncertainty="high"))   # never promotes
    recs = eng.recommendations()
    assert len(recs) == 1
    intent = OptimizationEngine.plan(recs[0])
    assert intent.reason.type == "recommendation"
    assert recs[0].to_dict()["executes"] is False            # §211


# ---- Phase J: federation ----------------------------------------------

def test_federation_summary_and_secret_boundary():
    node = NodeManifest(node_id="n1", capabilities=["fleet"],
                        data_freshness="fresh")
    s = export_summary(node, {"services": ["a", "b"], "cost": 10},
                       "internal")
    assert s["action"] == "aggregate"                        # §310
    assert "services.count" in s["payload"]
    sec = export_summary(node, {"api_key": "abc"}, "public")
    assert sec["action"] == "deny"
    assert sec["reason"] == "PF-FED-SECRET-BOUNDARY"         # §302
    denied = export_summary(node, {"x": 1}, "restricted")
    assert denied["action"] == "deny"


def test_federated_query_local_authority():
    nodes = [NodeManifest(node_id="n1"), NodeManifest(node_id="n2")]
    r = federated_query(nodes, lambda n, q: {"answered": True,
                                             "items": []}, "unowned")
    assert r["coverage"] == 1.0 and r["nodes"] == 2
    assert all(n.authority == "local" for n in nodes)        # §172


# ---- Phase K: AI platform ----------------------------------------------

def test_ai_unit_economics_denominator_and_detection():
    r = ai_unit_economics(1000.0, tokens=None, inferences=None)
    assert r["tokens_metric"] == "unknown"                   # §295
    r2 = ai_unit_economics(1000.0, tokens=2_000_000)
    assert r2["cost_per_1m_tokens"] == 500.0
    w = detect_ai_workloads([{"id": "inf-1", "resources": {
        "limits": {"nvidia.com/gpu": 2}}}])
    assert w[0]["gpu_count"] == 2
    pool = GPUCapacity(pool_id="p1", count=8, allocated=7,
                       utilization=95)
    risks = ai_capacity_risk([pool])
    assert any(r["risk"] == "gpu-saturation" for r in risks["risks"])


# ---- Phase L: economy ---------------------------------------------------

def test_fleet_pack_never_full_dump():
    items = [{"big": "x" * 500} for _ in range(20)]
    pack = fleet_context_pack({"team": "pay"}, org_summary={"o": 1},
                              cluster_details=items,
                              budgets={"cluster": 400})
    assert pack["full_fleet_loaded"] is False                # §214
    assert pack["deferred"]                                  # overflow→drill
    d = drill_down(pack, "cluster", items, budget=400)
    assert d["deferred"] >= 1


# ---- DX guard ------------------------------------------------------------

def test_no_person_metrics_guard():
    bad = guard_no_person_metrics({"team": {"developer_score": 3}})
    assert bad
    ok = guard_no_person_metrics(dx_metrics(
        [{"type": "provision", "wait_s": 5}]))
    assert ok == []
