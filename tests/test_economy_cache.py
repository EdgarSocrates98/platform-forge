"""Multilayer economy cache — §35–55."""

from __future__ import annotations

import pytest

from platformforge.economy.cache import LAYER_DEPS, CacheStore, cache_key, content_hash


@pytest.fixture
def store(tmp_path):
    return CacheStore(tmp_path)


DEPS = {"artifact_hash": "a1", "extractor_version": "e1",
        "rule_catalog_hash": "r1", "knowledge_hash": "k1",
        "runtime_version": "py312", "config_hash": "c1",
        "policy_hash": "p1", "engine_version": "v1",
        "evidence_hash": "ev1", "policy_version": "pv1",
        "risk_profile": "low"}


class TestContentAddressing:
    def test_key_binds_layer_deps_only(self):
        k1 = cache_key("fact", "s", DEPS)
        d2 = dict(DEPS, rule_catalog_hash="r2")
        assert cache_key("fact", "s", d2) == k1   # facts don't bind rules
        assert cache_key("finding", "s", d2) != \
            cache_key("finding", "s", DEPS)       # findings do

    def test_content_hash_stable(self):
        assert content_hash({"a": 1}) == content_hash({"a": 1})


class TestSelectiveInvalidation:
    def test_rules_change_keeps_facts_misses_findings(self, store):
        store.put("artifact", "repo", {"blob": 1}, DEPS)
        store.put("fact", "repo", ["f1"], DEPS)
        store.put("finding", "repo", ["F-1"], DEPS)
        new = dict(DEPS, rule_catalog_hash="r2")
        dec, facts = store.get("fact", "repo", new)
        assert dec.state == "hit" and facts == ["f1"]
        dec, _art = store.get("artifact", "repo", new)
        assert dec.state == "hit"
        dec, _ = store.get("finding", "repo", new)
        assert dec.state == "invalid" and "rule_catalog_hash" in dec.changed_deps

    def test_invalidate_dep_removes_only_bound_layers(self, store):
        for layer in ("fact", "finding", "context"):
            store.put(layer, "x", [1], DEPS)
        out = store.invalidate_dep("knowledge_hash", "k2")
        assert set(out["unaffected_layers"]) == {
            "artifact", "fact", "graph", "decision"}
        assert any(r.startswith("finding/") for r in out["removed"])
        assert any(r.startswith("context/") for r in out["removed"])
        dec, _ = store.get("fact", "x", dict(DEPS, knowledge_hash="k2"))
        assert dec.state == "hit"

    def test_reuse_plan_partial(self, store):
        store.put("fact", "s", [1], DEPS)
        store.put("finding", "s", [2], DEPS)
        plan = store.reuse_plan(dict(DEPS, rule_catalog_hash="r2"),
                                {"fact": "s", "finding": "s"})
        assert plan.state == "partial-reuse"
        assert plan.reusable_layers == ["fact"]
        assert plan.invalidated_layers == ["finding"]


class TestFreshness:
    def test_ttl_stale(self, store):
        store.put("artifact", "s", {"x": 1}, DEPS, ttl_s=10)
        dec, _ = store.get("artifact", "s", DEPS, now=1e10)
        assert dec.state == "stale"

    def test_live_conclusion_needs_freshness(self, store):
        store.put("analysis", "s", {"verdict": "ok"}, DEPS, live=True,
                  observed_at=1000.0, freshness_s=60)
        dec, v = store.get("analysis", "s", DEPS, now=1030.0)
        assert dec.state == "hit" and v["verdict"] == "ok"
        dec, _ = store.get("analysis", "s", DEPS, now=2000.0)
        assert dec.state == "stale"

    def test_live_without_freshness_is_stale(self, store):
        store.put("analysis", "s", {"x": 1}, DEPS, live=True)
        dec, _ = store.get("analysis", "s", DEPS)
        assert dec.state == "stale"


class TestSecurity:
    def test_sensitive_payload_refused(self, store):
        dec = store.put("context", "s", {"token": "abc"}, DEPS,
                        sensitive=True)
        assert dec.state == "invalid" and "never cached" in dec.reason
        assert store.stats()["refused"] == 1

    def test_decision_requires_safety_deps(self, store):
        dec = store.put("decision", "route:s", {"mode": "single"},
                        {"artifact_hash": "a1"})
        assert dec.state == "invalid"
        dec = store.put("decision", "route:s", {"mode": "single"}, DEPS)
        assert dec.state == "hit"

    def test_no_approval_layer(self):
        assert "approval" not in LAYER_DEPS


class TestMaintenance:
    def test_stats_and_gc(self, store):
        store.put("artifact", "a", {"x": 1}, DEPS)
        store.put("artifact", "b", {"x": 2}, DEPS, ttl_s=1)
        s = store.stats()
        assert s["puts"] == 2 and s["entries"] == 2
        store.get("artifact", "a", DEPS)
        assert store.stats()["hits"] == 1
        out = store.gc(now=9e18)
        assert len(out["gc_removed"]) == 1 and out["remaining"] == 1
