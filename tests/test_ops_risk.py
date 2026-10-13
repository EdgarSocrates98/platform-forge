"""Phase C gates — risk classes, reversibility, unknown≠low."""

from platformforge.ops.risk import assess, classify_reversibility


def test_read_only_action_r0():
    r = assess("terraform.plan", {},
               {"environment": "dev", "reversibility": "fully-reversible",
                "criticality": "low", "blast_radius": "low",
                "security_impact": "low", "identity_impact": "low",
                "network_exposure": "low", "data_impact": "low",
                "availability_impact": "low", "cost_impact": "low",
                "rollback_confidence": "high",
                "observation_freshness": "fresh",
                "coverage_completeness": "complete"})
    assert r.risk_class == "R0"
    assert not r.blocks_autonomy


def test_prod_escalates_to_r3():
    r = assess("kubernetes.scale", {"replicas": 5},
               {"environment": "prod", "reversibility": "fully-reversible"})
    assert r.risk_class == "R3"
    assert any("prod" in e for e in r.escalation_reasons)


def test_irreversible_escalates_r4():
    r = assess("kubernetes.scale", {"replicas": 1},
               {"environment": "dev", "reversibility": "irreversible"})
    assert r.risk_class == "R4"


def test_unknown_dims_block_autonomy():
    r = assess("kubernetes.scale", {"replicas": 1},
               {"environment": "dev", "reversibility": "fully-reversible"})
    # unknowns present (criticality etc. not supplied)
    assert "criticality" in r.unknowns
    assert r.blocks_autonomy


def test_unknown_action_is_r5():
    r = assess("shell.run", {"cmd": "rm -rf /"}, {"environment": "dev"})
    assert r.risk_class == "R5"
    assert "unlisted-action:shell.run" in r.unknowns


def test_destructive_params_escalate():
    r = assess("terraform.apply_saved_plan", {"mode": "destroy"},
               {"environment": "dev", "reversibility": "irreversible",
                "data_present": True})
    assert r.risk_class in ("R4", "R5")


def test_reversibility_classification():
    assert classify_reversibility("kubernetes.scale") == "fully-reversible"
    assert classify_reversibility("git.open_pr") == "conditionally-reversible"
    assert classify_reversibility("mystery.action") == "unknown"
