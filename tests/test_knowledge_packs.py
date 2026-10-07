"""Cycle 2.1 §60–68 — knowledge pack contract."""

import pytest

from platformforge.knowledge.packs import Pack, PackRegistry


def test_packs_load_and_hash():
    reg = PackRegistry.default()
    assert len(reg.packs) >= 10
    for p in reg.packs.values():
        assert p.content_hash and len(p.content_hash) == 16
        assert p.claims


def test_contract_check_clean():
    reg = PackRegistry.default()
    c = reg.contract_check()
    assert c["ok"], c["problems"]
    assert c["consumed"] == len(reg.packs)


def test_for_rule_lookup():
    reg = PackRegistry.default()
    rules = {p.pack_id for p in reg.for_rule("PF-XR-001")}
    assert rules  # crossplane packs feed PF-XR-001
    assert {p.pack_id for p in reg.for_rule("PF-K8S-030")}


def test_for_analyzer_lookup():
    reg = PackRegistry.default()
    assert reg.for_analyzer("crossplane")
    assert reg.for_analyzer("k8s")
    assert not reg.for_analyzer("nonexistent-analyzer")


def test_schema_required(tmp_path):
    (tmp_path / "bad.yaml").write_text(
        "id: x\ndomain: k8s\nsources: [kubernetes-docs]\nclaims: []\n")
    # wrong/missing schema → not loaded (registry skips non-pack yaml)
    reg = PackRegistry(tmp_path)
    assert reg.packs == {}


def test_pack_rejects_missing_fields():
    with pytest.raises(ValueError):
        Pack.from_dict({"schema": "platformforge/knowledge/v1",
                        "id": "x"})


def test_hash_detects_drift():
    base = {"schema": "platformforge/knowledge/v1", "id": "p",
            "domain": "k8s", "sources": ["kubernetes-docs"],
            "claims": [{"id": "c1", "statement": "a"}]}
    p1 = Pack.from_dict(dict(base))
    p2 = Pack.from_dict(dict(base, claims=[{"id": "c1",
                                            "statement": "changed"}]))
    assert p1.content_hash != p2.content_hash


def test_unconsumed_pack_flagged(tmp_path):
    (tmp_path / "dead.yaml").write_text(
        "schema: platformforge/knowledge/v1\nid: dead\ndomain: x\n"
        "sources: [kubernetes-docs]\n"
        "claims: [{id: c, statement: s}]\nused_by: {}\n")
    reg = PackRegistry(tmp_path)
    c = reg.contract_check()
    assert not c["ok"]
    assert any(p["issue"] == "unconsumed" for p in c["problems"])
