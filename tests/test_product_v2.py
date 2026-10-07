"""Cycle 2 Phase F — golden paths, maturity v2, scorecards v2."""
from __future__ import annotations

from platformforge.product.golden_paths import (analyze_paths, capabilities,
                                              describe, load_library)
from platformforge.product.maturity import maturity_report
from platformforge.product.scorecards import scorecard


def test_library_contract():
    lib = load_library()
    assert len(lib["paths"]) == 7 and not lib["invalid"]
    for p in lib["paths"]:
        eh = p.escape_hatches
        assert {"happy_path", "supported_customizations",
                "escape_hatch", "unsupported_state"} <= set(eh)


def test_describe_and_capability_contract():
    d = describe("rest-service")
    assert d["slo"]["availability"] == 99.9
    caps = capabilities()
    assert all(c["approval_required"] and not c["mutates"]
               for c in caps["capabilities"])
    assert describe("nonexistent")["refusal"] == "PF-PATH-UNKNOWN"


def test_analyze_paths_gaps():
    facts = [
        {"fact_id": "PF-K8S-1", "kind": "k8s.workload", "tier": 3,
         "location": "a.yaml::default/api", "attrs": {"labels": {}}},
        {"fact_id": "PF-GO-1", "kind": "gitops.argocd_app", "tier": 3,
         "location": "app.yaml::argocd/x",
         "attrs": {"automated_sync": False}},
        {"fact_id": "PF-CICD-1", "kind": "gha.workflow", "tier": 3,
         "location": "a", "attrs": {"name": "ci"}},
        {"fact_id": "PF-CICD-2", "kind": "gha.workflow", "tier": 3,
         "location": "b", "attrs": {"name": "CI"}},
    ]
    gaps = {g["gap"] for g in analyze_paths(facts)["gaps"]}
    assert {"missing_ownership", "missing_automation",
            "duplicate_workflow"} <= gaps


def test_maturity_v2_provenance():
    sig = {"investment": [{"signal": "dedicated_team",
                           "provenance": "observed"},
                          {"signal": "funded"}]}
    out = maturity_report(sig)
    inv = out["aspects"]["investment"]
    assert inv["level"] == "provisional"          # only 1 of 2 observed
    assert inv["declared_level"] == "operational"
    assert inv["overclaimed"] is True


def test_scorecard_unknown_ne_zero():
    findings = [{"rule_id": "PF-K8S-002", "status": "violated",
                 "severity": "high", "location": "svc/a"}]
    out = scorecard(findings, evidence_domains={"k8s"})
    card = out["scorecards"]["svc/a"]
    assert card["axes"]["deployment"]["status"] == "measured"
    assert card["axes"]["deployment"]["score"] == 93
    assert card["axes"]["cost"]["status"] == "unknown"
    assert card["axes"]["cost"]["score"] is None
    assert "cost" in card["unknown_axes"]
