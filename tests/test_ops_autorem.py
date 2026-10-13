"""Phase N gates — auto-remediation eligibility."""

from platformforge.ops.autorem import evaluate_eligibility


def _kw(**over):
    kw = {"action": "kubernetes.scale", "risk_class": "R2",
          "capability_autonomy": "A5", "environment": "lab",
          "evidence_tier": "confirmed",
          "observation": {"captured_at": "2999-01-01T00:00:00Z",
                          "coverage": {"complete": True}},
          "max_observation_age_s": 900,
          "source_of_truth": {"resolved": True, "source": "git"},
          "reversibility": "fully-reversible",
          "simulation_outcome": "pass", "policy_decision": "allow",
          "unresolved_identities": 0, "conflicting_operations": 0,
          "verification_available": True, "rollback_ready": True}
    kw.update(over)
    return kw


def test_all_green_is_eligible():
    e = evaluate_eligibility(**_kw())
    assert e.eligible and not e.failed


def test_prod_never_eligible():
    e = evaluate_eligibility(**_kw(environment="prod"))
    assert not e.eligible and "non-prod" in e.failed


def test_r3_never_eligible():
    e = evaluate_eligibility(**_kw(risk_class="R3"))
    assert not e.eligible


def test_any_unknown_fails_closed():
    e = evaluate_eligibility(**_kw(evidence_tier=None,
                                   reversibility="unknown",
                                   simulation_outcome=None))
    assert not e.eligible
    assert "high-confidence-evidence" in e.failed
    assert "simulation-passed" in e.failed
    assert e.refusal["refusal"] == "PF-OPS-AUTO-INELIGIBLE"


def test_stale_observation_fails():
    e = evaluate_eligibility(**_kw(
        observation={"captured_at": "2000-01-01T00:00:00Z",
                     "coverage": {"complete": True}}))
    assert "fresh-complete-observation" in e.failed


def test_partial_coverage_fails():
    e = evaluate_eligibility(**_kw(
        observation={"captured_at": "2999-01-01T00:00:00Z",
                     "coverage": {"complete": False}}))
    assert "fresh-complete-observation" in e.failed


def test_unresolved_sot_fails():
    e = evaluate_eligibility(**_kw(
        source_of_truth={"resolved": False}))
    assert "source-of-truth-resolved" in e.failed


def test_shadow_policy_not_enough():
    e = evaluate_eligibility(**_kw(policy_decision="would_allow"))
    assert "policy-allow" in e.failed


def test_conflicts_block():
    e = evaluate_eligibility(**_kw(conflicting_operations=2))
    assert "no-conflicts" in e.failed
