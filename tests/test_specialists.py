"""Phase E — 15 domain specialists + the §99 finding contract."""

from __future__ import annotations

from platformforge.agents import OUTPUT_STATUSES, finding, grade
from platformforge.agents.roster import AGENTS

EXPECTED_SPECIALISTS = {
    "platform-iac-specialist",
    "platform-kubernetes-specialist",
    "platform-gitops-specialist",
    "platform-sre-specialist",
    "platform-security-specialist",
    "platform-finops-specialist",
    "platform-graph-specialist",
    "platform-aws-specialist",
    "platform-crossplane-specialist",
    "platform-fleet-specialist",
    "platform-policy-specialist",
    "platform-capacity-specialist",
    "platform-product-specialist",
    "platform-ai-infra-specialist",
    "platform-federation-specialist",
}


def test_all_fifteen_specialists_exist():
    specialists = {a.name for a in AGENTS.values()
                   if a.role == "specialist"}
    assert EXPECTED_SPECIALISTS <= specialists
    for name in EXPECTED_SPECIALISTS:
        assert AGENTS[name].contract_errors() == [], name


def test_specialists_are_read_only_and_bounded():
    for a in AGENTS.values():
        if a.role != "specialist":
            continue
        assert a.access == "read-only", a.name
        assert not a.delegates_to, \
            f"{a.name}: specialists do not spawn (§68)"
        assert a.required_evidence, a.name


def test_finding_shape_and_status():
    f = finding("platform-iac-specialist", "state has drift",
                status="confirmed", evidence=("F-1",),
                coverage=0.8, freshness="current",
                confidence="high", next_action="judge drift rules")
    for k in ("claim", "status", "evidence", "coverage", "freshness",
              "confidence", "limitations", "next_action"):
        assert k in f
    assert f["status"] == "confirmed"


def test_finding_without_evidence_demoted():
    f = finding("platform-aws-specialist", "account is clean",
                status="confirmed")
    assert f["status"] == "unsupported"
    assert f["demoted"] and f["demoted_from"] == "confirmed"
    assert any("demoted" in l for l in f["limitations"])


def test_finding_bad_status_refused():
    out = finding("x", "claim", status="maybe")
    assert out["refusal"].startswith("PF-AGENT-")
    for s in OUTPUT_STATUSES:
        assert isinstance(s, str)


def test_grade_surfaces_unsupported():
    fs = [finding("a", "ok", status="confirmed", evidence=("F-1",)),
          finding("b", "gap", status="unresolved"),
          finding("c", "nope", status="confirmed")]
    out = grade(fs)
    assert out["total"] == 3
    assert out["by_status"]["unsupported"] == 1
    assert out["demoted"] == 1
    assert out["ok"]
