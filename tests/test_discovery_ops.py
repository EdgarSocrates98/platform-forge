"""lf-0037: §6.2 discovery ops — manifest map, retrieval verbs."""

from __future__ import annotations


def test_ops_map_covers_all_eight():
    from platformforge import discovery_ops

    assert set(discovery_ops.ops()) == {
        "capabilities.list", "protocol.describe", "rules.search", "rules.get",
        "knowledge.search", "knowledge.get", "context.build", "health.check",
    }
    assert {c["id"] for c in discovery_ops.commands()} == set(discovery_ops.ops().values())


def test_rules_search_get():
    from platformforge import discovery

    p = discovery.rules_search(query="cost", limit=2)
    assert p["total"] >= 1
    rid = p["rules"][0]["id"]
    assert discovery.rules_get(rid)["found"] is True
    assert discovery.rules_get("PF-NOPE-000")["found"] is False


def test_knowledge_search_get():
    from platformforge import discovery

    out = discovery.knowledge_search("autoscaling", limit=2)
    assert out["documents_total"] >= 1
    for d in out["documents"]:
        assert len(d["sha256"]) == 64 and d["matched_lines"] >= 1
    got = discovery.knowledge_get(out["documents"][0]["ref"])
    assert len(got["document"]["sha256"]) == 64


def test_capabilities_context_pack_deterministic():
    from platformforge import discovery

    caps = discovery.capabilities()
    assert caps["rules"]["count"] > 0 and len(caps["operations"]) == 8
    p1 = discovery.context_pack("kubernetes", rules_limit=5, knowledge_limit=3)
    p2 = discovery.context_pack("kubernetes", rules_limit=5, knowledge_limit=3)
    assert p1["pack_sha256"] == p2["pack_sha256"]
    assert len(p1["rules"]) <= 5 and len(p1["knowledge"]["documents"]) <= 3
