"""Phase P (§192–207) + Q (§161–165) — fleet/collection economy and
quality-per-cost."""

from __future__ import annotations

from platformforge.economy.cache import CacheStore
from platformforge.economy.collection import (
    CollectionEconomyPlan,
    coverage_on_exhaustion,
    evidence_gate,
    fleet_delta,
    fleet_query_cache_get,
    fleet_query_cache_put,
    provider_call_roi,
)
from platformforge.economy.qpt import quality_per_cost
from platformforge.knowledge.select import search_knowledge, select_packs


class FakePack:
    def __init__(self, pid, domain, applies=None, claims=()):
        self.pack_id = pid
        self.domain = domain
        self.applies_to = applies or {}
        self.claims = [type("C", (), {"statement": s}) for s in claims]


def _snap(members):
    return {"members": members}


# --- collection ----------------------------------------------------------

def test_collection_plan_defaults():
    p = CollectionEconomyPlan()
    assert p.inventory_first and p.evidence_gate
    assert p.to_dict()["schema"] == "platformforge/collection-economy-plan/v1"


def test_evidence_gate_refuses_when_local_answers():
    r = evidence_gate("posture", {"answers": ["a"], "coverage": 0.9})
    assert r["decision"] == "refuse_live_call"
    assert r["code"] == "PF-ECONOMY-LIVE-UNNECESSARY"


def test_evidence_gate_allows_runtime_truth():
    r = evidence_gate("posture", {"coverage": 0.1},
                      runtime_truth_needed=True)
    assert r["decision"] == "live_call_justified"


def test_roi_zero_calls_is_unresolved_not_zero():
    assert provider_call_roi(0, 10, 0.5)["state"] == "unresolved"
    r = provider_call_roi(4, 12, 0.6)
    assert r["facts_per_call"] == 3.0 and r["basis"] == "measured"


def test_coverage_partial_on_exhaustion():
    r = coverage_on_exhaustion(30, 100)
    assert r["state"] == "partial" and r["coverage"] == 0.3


def test_fleet_query_cache_keyed_by_snapshot(tmp_path):
    store = CacheStore(tmp_path / "c")
    s1, s2 = _snap({"k8s:a": {"ref": "h1"}}), _snap({"k8s:a": {"ref": "h2"}})
    fleet_query_cache_put(store, s1, "public-services", ["svc-a"])
    hit = fleet_query_cache_get(store, s1, "public-services")
    assert hit["decision"]["state"] == "hit" and hit["payload"] == ["svc-a"]
    # new snapshot hash → miss, never stale
    miss = fleet_query_cache_get(store, s2, "public-services")
    assert miss["decision"]["state"] == "miss"


def test_fleet_delta_lists_changes():
    a = _snap({"a": "r1", "b": "r2", "c": "r3"})
    b = _snap({"a": "r1", "b": "rX", "d": "r4"})
    d = fleet_delta(a, b)
    assert d["added"] == ["d"] and d["removed"] == ["c"]
    assert d["changed"] == ["b"] and d["unchanged"] == 1


# --- knowledge select -----------------------------------------------------

def test_select_packs_domain_and_versions():
    packs = [
        FakePack("k8s-deps", "kubernetes",
                 {"versions": {"kubernetes": ">=1.22"}},
                 ["api removed"]),
        FakePack("aws-iam", "aws", {}, ["wildcard"]),
    ]
    r = select_packs(packs, domain="kubernetes",
                     versions={"kubernetes": "1.29"}, max_packs=4)
    assert [v["pack_id"] for v in r["selected"]] == ["k8s-deps"]
    assert r["skipped"][0]["pack_id"] == "aws-iam"


def test_select_packs_budget_overflow():
    packs = [FakePack(f"p{i}", "kubernetes") for i in range(5)]
    r = select_packs(packs, domain="kubernetes", max_packs=3)
    assert len(r["selected"]) == 3 and r["overflow"] == 2


def test_select_packs_stale_under_high_risk_flagged():
    packs = [FakePack("k8s", "kubernetes")]
    r = select_packs(packs, domain="kubernetes", risk="high",
                     freshness_of=lambda _p: "stale")
    assert "review_needed" in r["selected"][0]["reason"]


def test_search_tiers():
    packs = [FakePack("k8s-deps", "kubernetes", claims=["v1beta gone"]),
             FakePack("iam", "aws")]
    assert search_knowledge(packs, "k8s-deps")["tier"] == 0
    assert search_knowledge(packs, "v1beta")["tier"] == 1
    r = search_knowledge(packs, "nomatch")
    assert r["tier"] == 2 and r["packs"] == []


# --- QPT v3 ---------------------------------------------------------------

def _fake_qpt():
    return {"task": "t", "verdict": "beneficial",
            "quality": {"floors_ok": {"a": True}},
            "baseline": {"estimated_tokens": 1000,
                         "model_context_bytes": 4000},
            "optimized": {"estimated_tokens": 400,
                          "model_context_bytes": 1600}}


def test_qpc_dimensions_and_composite():
    r = quality_per_cost(_fake_qpt(),
                         baseline_usage={"tool_calls": 10, "agents": 5},
                         optimized_usage={"tool_calls": 4, "agents": 1})
    d = r["dimensions"]
    assert d["tokens"]["reduction"] == 0.6
    assert d["tool_calls"]["reduction"] == 0.6
    assert d["money"]["state"] == "unresolved"
    assert d["model_calls"]["state"] == "unresolved"
    assert r["composite"]["decomposable"]
    assert 0 < r["composite"]["cost_reduction_mean"] < 1


def test_qpc_no_claim_when_floor_fails():
    q = _fake_qpt()
    q["quality"]["floors_ok"] = {"a": False}
    q["verdict"] = "optimization_not_beneficial"
    r = quality_per_cost(q)
    assert not r["quality_floors_ok"]
    assert "no savings claim" in r["honest_claim"]
