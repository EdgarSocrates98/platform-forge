"""Cycle 5 Phase P — adversarial review E1–E12 (§350–361).

Each test answers one spec question with executable evidence — the
unsafe reading must fail closed, not just be discouraged.
"""
from datetime import datetime, timedelta, timezone

# ── E1: can partial fleet data appear complete? ────────────────────

def test_e1_partial_never_complete():
    from platformforge.fleet.models import FleetSnapshot, MemberObservation
    snap = FleetSnapshot(
        fleet_id="f",
        member_observations=[
            MemberObservation(member_id="a", status="observed",
                              coverage=1.0),
            MemberObservation(member_id="b",
                              status="permission-limited",
                              coverage=0.4),
            MemberObservation(member_id="c", status="unreachable")])
    d = snap.to_dict()
    assert snap.coverage < 1.0
    assert d["member_observations"][1]["status"] == \
        "permission-limited"
    assert d["member_observations"][2]["status"] == "unreachable"


def test_e1_stale_cannot_seed_fresh_conclusion():
    from platformforge.analytics.history import HistoryEngine
    eng = HistoryEngine()
    old = (datetime.now(timezone.utc) - timedelta(days=30))
    eng.ingest_events("incident", [
        {"ts": old.isoformat(), "subject": "s", "type": "x"}], "t")
    assert eng.events("24h") == []           # stale ≠ current truth
    assert len(eng.events("90d")) == 1       # still visible, as stale


# ── E2: can a repeated pattern be called causality? ────────────────

def test_e2_pattern_never_causal():
    from platformforge.analytics.history import HistoryEngine
    eng = HistoryEngine()
    now = datetime.now(timezone.utc)
    eng.ingest_events("incident", [
        {"ts": (now - timedelta(days=i)).isoformat(),
         "subject": "s", "type": "boom"} for i in range(6)], "t")
    p = eng.patterns("90d")[0].to_dict()
    assert not p.get("causal_claim")
    assert "correlation is not causality" in p["limitations"]
    assert p["hypothesis"] is not None or "hypothesis" in p


# ── E3: can a low-usage resource be labeled deletable? ─────────────

def test_e3_idle_never_deletable():
    from platformforge.analytics.finops_v4 import idle_resources, rightsizing
    for r in idle_resources([{"id": "x", "cpu_util": 0,
                              "requests_30d": 0, "attached": False}]):
        assert not r.get("deletable")
    rs = rightsizing({"id": "w", "cpu_util": 2, "memory_util": 3,
                      "slo_headroom": 0.9})
    if rs:
        assert not rs.get("deletable") and "delete" not in \
            str(rs.get("recommendation", "")).lower()


# ── E4: can centrality become criticality accidentally? ────────────

def test_e4_centrality_not_criticality():
    from platformforge.analytics.reliability import blast_concentration
    from platformforge.graph.model import Edge, Graph, Node
    g = Graph()
    for n in "abcd":
        g.add_node(Node.make("service", n))
    for d in "bcd":
        g.add_edge(Edge("service/a", f"service/{d}", "depends_on"))
    hub = blast_concentration(g)[0]
    assert hub["declared_criticality"] is None   # not assigned
    assert "criticality" in hub["note"]


# ── E5: can a policy w/ exceptions be called bad w/o evidence? ─────

def test_e5_exceptions_need_success_evidence():
    from platformforge.analytics.policyintel import false_positive_candidates, policy_metrics
    m = policy_metrics(
        [{"policy": "p", "decision": "deny"}] * 4,
        exceptions=[{"policy": "p"}] * 6)
    # many exceptions, zero recorded successful outcomes → no flag
    assert false_positive_candidates(m, {"p": 0}) == []
    assert false_positive_candidates(m, {}) == []
    # with outcomes the signal is still review-required, not a verdict
    fps = false_positive_candidates(m, {"p": 5})
    assert fps and fps[0]["verdict"] == "review-required"
    assert "exception ≠ false positive" in fps[0]["limitations"]


# ── E6: can missing cost data become zero? ─────────────────────────

def test_e6_missing_cost_is_unknown():
    from platformforge.analytics.finops_v4 import cost_hierarchy, unit_economics
    h = cost_hierarchy([{"amount": 100}])     # no allocation keys
    assert h["unallocated"] >= 100
    ue = unit_economics(100, denominator=None, unit="request")
    assert ue["value"] == "unknown" and ue["confidence"] == "low"


# ── E7: can optimization bypass operations governance? ─────────────

def test_e7_optimization_terminates_at_intent():
    from platformforge.ops.models import ChangeIntent
    from platformforge.optimize.engine import OptimizationEngine
    from platformforge.optimize.models import OptimizationRecommendation
    methods = {m for m in dir(OptimizationEngine)
               if not m.startswith("_")}
    assert not methods & {"execute", "apply", "envelope", "mint"}
    ci = OptimizationEngine.plan(OptimizationRecommendation(
        recommendation_id="r", type="cost", scope={"s": "x"},
        confidence="high"))
    assert isinstance(ci, ChangeIntent)
    # the intent still must pass plan→policy→approve→execute→verify
    assert ci.reason.type == "recommendation"


# ── E8: can federation leak credentials? ───────────────────────────

def test_e8_federation_no_credential_leak():
    from platformforge.federation.node import NodeManifest, export_summary
    node = NodeManifest(node_id="n", capabilities=[])
    for cls in ("public", "internal", "restricted", "confidential"):
        s = export_summary(node, {"db": {"password": "hunter2"}}, cls)
        assert "hunter2" not in str(s)


# ── E9: can a remote node gain execution authority? ────────────────

def test_e9_remote_no_execution():
    from platformforge.federation.node import NodeManifest, federated_query
    from platformforge.ops.registry import delegation_contract, validate_delegate_request
    assert all(x in delegation_contract()["refuses"] for x in
               ("direct-execution", "approval-minting",
                "shell-command", "generic-provider-call",
                "full-fleet-dump"))
    for bad in ("direct-execution", "approval-minting",
                "credential-transfer", "shell-command"):
        assert validate_delegate_request(
            {"kind": bad})["refusal"] == "PF-OPS-CROSSFORGE-REFUSED"
    out = federated_query([NodeManifest(node_id="n1")],
                          lambda n, q: {"answered": True, "v": 1},
                          "unowned")
    assert "no execution authority" in out["note"]


# ── E10: can developer analytics become surveillance? ──────────────

def test_e10_dx_never_personal():
    from platformforge.analytics.dx import FORBIDDEN_METRICS, dx_metrics, guard_no_person_metrics
    m = dx_metrics([
        {"path": "p", "requested_at": "2025-11-01T00:00:00Z",
         "ready_at": "2025-11-01T00:10:00Z", "status": "provisioned",
         "person": "alice"}])                 # hostile input
    assert guard_no_person_metrics(m) == []
    flat = {k for v in m.values() if isinstance(v, dict)
            for k in v} | set(m)
    assert not flat & set(FORBIDDEN_METRICS)


# ── E11: AI unit econ without denominator? ─────────────────────────

def test_e11_ai_econ_needs_denominator():
    from platformforge.aiplat.models import ai_unit_economics
    ue = ai_unit_economics(5000)
    assert "cost_per_1m_tokens" not in ue
    assert "cost_per_inference" not in ue
    ue2 = ai_unit_economics(5000, tokens=2_000_000)
    assert ue2.get("cost_per_1m_tokens") == 2500.0


# ── E12: can generated optimization masquerade as fact? ────────────

def test_e12_recommendation_not_measured_fact():
    from platformforge.optimize.models import OptimizationRecommendation
    r = OptimizationRecommendation(
        recommendation_id="x", type="cost", scope={"s": "y"})
    d = r.to_dict()
    assert d["confidence"] in ("low", "medium", "high")
    assert "evidence" in d
    # recs always declare they are proposals, not observations
    assert d.get("kind") != "fact" and "recommendation" in \
        d.get("schema", "recommendation")
