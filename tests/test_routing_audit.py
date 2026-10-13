"""§69–§84 — routing/context audit over the real-world corpus."""
from platformforge.cases.context_audit import audit_corpus as ctx_corpus
from platformforge.cases.routing_audit import audit_corpus, champion_challenger

ROOT = ".platformforge/cases"


def test_route_audit_covers_every_case():
    r = audit_corpus(ROOT, ledger=False)
    assert r["cases"] >= 15
    assert all(d["router_input"]["domains"] for d in r["decisions"])


def test_no_under_routing_on_security_cases():
    r = audit_corpus(ROOT, ledger=False)
    for d in r["decisions"]:
        if d["router_input"]["security_sensitive"]:
            assert "platform-security-reviewer" in d["reviewers"], d["case"]
            assert not any("under-routing" in f for f in d["flags"])


def test_no_over_routing_on_single_domain():
    r = audit_corpus(ROOT, ledger=False)
    singles = [d for d in r["decisions"]
               if len(d["router_input"]["domains"]) == 1]
    assert singles
    for d in singles:
        assert not any("over-routing" in f for f in d["flags"]), d["case"]


def test_every_agentic_route_has_verifier():
    r = audit_corpus(ROOT, ledger=False)
    for d in r["decisions"]:
        if d["mode"] != "deterministic":
            assert d["verifier"] == "platform-verifier"


def test_champion_challenger_scores_correctness():
    r = champion_challenger(ROOT)
    for row in r["cases"]:
        assert row["champion"]["evidence_recall"] == 1.0, row["case"]
        assert row["champion"]["correctness"] == ["full"]


def test_context_audit_measures_bytes():
    r = ctx_corpus(ROOT)
    t = r["totals"]
    assert t["input_bytes"] > 0
    assert t["relevant_bytes"] <= t["input_bytes"]
    assert 0.0 <= t["avg_unused_context_ratio"] <= 1.0
    for a in r["cases"]:
        assert a["relevant_bytes"] + a["unused_bytes"] == a["input_bytes"]
