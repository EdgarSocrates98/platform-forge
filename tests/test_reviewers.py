"""Phase F — reviewers: declared checklists, pass|gaps|issues only."""

from __future__ import annotations

from platformforge.agents.reviewers import (
    OPS_SAFETY_CHECKLIST,
    architecture_review,
    ops_safety_review,
    privacy_review,
    security_review,
)
from platformforge.agents.roster import AGENTS

REVIEWERS = ("platform-evidence-reviewer", "platform-economy-reviewer",
             "platform-operations-safety-reviewer",
             "platform-security-reviewer",
             "platform-architecture-reviewer",
             "platform-privacy-reviewer",
             "platform-task-spec-reviewer")


def test_all_reviewers_exist_and_lint():
    reviewers = {a.name: a for a in AGENTS.values()
                 if a.role == "reviewer"}
    for name in REVIEWERS:
        assert name in reviewers, name
        assert reviewers[name].contract_errors() == []


def test_ops_safety_all_items_checked():
    full = {k: True for k in ("source_of_truth", "risk", "approver",
                              "rollback", "expected_delta", "locks",
                              "idempotent", "verify")}
    out = ops_safety_review(full)
    assert out["verdict"] == "pass"
    assert out["checked"] == list(OPS_SAFETY_CHECKLIST)
    gaps = ops_safety_review({"source_of_truth": True})
    assert gaps["verdict"] == "gaps"
    assert "rollback-material" in gaps["gaps"]
    assert "verification" in gaps["gaps"]


def test_security_review_rejects_raw_secrets_and_no_evidence():
    out = security_review({"claim": "safe", "secret_value": "x"})
    assert "issues" in out["verdict"] or out["verdict"] == "issues"
    assert any("secret" in i for i in out["issues"])
    assert any("evidence" in i for i in out["issues"])
    ok = security_review({"claim": "safe", "evidence": ["F-1"]})
    assert ok["verdict"] == "pass"


def test_architecture_review_needs_evidence_for_blast():
    out = architecture_review({"triggers": ("new-subsystem",)},
                              blast_radius=120)
    assert out["verdict"] == "objections"
    assert any("blast" in o for o in out["objections"])
    assert any("boundary" in o for o in out["objections"])
    ok = architecture_review({"triggers": (), "blast_evidence": True},
                             blast_radius=3)
    assert ok["verdict"] == "pass"


def test_privacy_review_surfaces_and_federation():
    out = privacy_review({"surface": "federation-export",
                          "raw_facts": True})
    assert out["verdict"] == "exposures"
    assert any("summaries" in e for e in out["exposures"])
    ok = privacy_review({"surface": "fleet-analytics",
                         "export_policy": "default",
                         "identifiers": ["team"]})
    assert ok["verdict"] == "pass"
