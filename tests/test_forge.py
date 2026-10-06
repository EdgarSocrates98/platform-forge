"""Phase 15 gate: capability manifest, A2A envelope, receipts."""

from platformforge.forge import Delegation, build_envelope, capability_manifest, verify_envelope
from platformforge.forge.delegate import result_receipt


def test_manifest_is_generated(tmp_path):
    m = capability_manifest()
    assert m["forge"] == "platform-forge"
    assert m["manifest"] == "platformforge/capability-manifest/v1"
    assert m["modes"]["read_only"] and not m["modes"]["cloud_mutation"]
    assert m["rule_count"] >= 40
    assert "platformforge_analyze" in m["tools"]
    assert "workload" in m["graph_vocab"]["node_kinds"]


def test_envelope_roundtrip():
    d = Delegation(from_forge="platform-forge", to_forge="api-forge",
                   task="audit openapi surface",
                   budget={"max_tokens": 4000})
    env = build_envelope(d)
    assert env["envelope"] == "platformforge/a2a-envelope/v1"
    v = verify_envelope(env)
    assert v["accepted"] is True
    bad = verify_envelope({"task": "x"})
    assert bad["accepted"] is False and bad["missing"]


def test_invalid_delegation_refused():
    env = build_envelope(Delegation("", "", ""))
    assert env["refusal"] == "platform.delegation.invalid"


def test_result_receipt():
    d = Delegation("platform-forge", "api-forge", "audit")
    env = build_envelope(d)
    r = result_receipt(env, {"summary": "done"},
                       evidence=[{"fact_id": "PF-IAC-1"}])
    assert r["receipt"] == "platformforge/result-receipt/v1"
    assert r["from_forge"] == "api-forge" and r["to_forge"] == "platform-forge"
    assert r["evidence_facts"]
