"""Case corpus + replay — §52–§68."""
from pathlib import Path

import yaml

from platformforge.cases.casefile import case_errors, discover_cases, load_case
from platformforge.cases.replay import replay_all, replay_case, validate_corpus

ROOT = ".platformforge/cases"


def test_corpus_discovers_both_tiers():
    cases = discover_cases(ROOT)
    tiers = {c.tier for c in cases}
    assert tiers == {"golden", "holdout"}
    assert len(cases) >= 10
    # every seeded case is structurally valid
    for c in cases:
        assert case_errors(c) == [], (c.id, case_errors(c))


def test_golden_and_holdout_are_disjoint():
    cases = discover_cases(ROOT)
    golden = {c.id for c in cases if c.tier == "golden"}
    holdout = {c.id for c in cases if c.tier == "holdout"}
    assert not (golden & holdout)


def test_replay_is_deterministic_and_passing():
    r = replay_all(ROOT)
    assert r["verdict"] == "pass", r["failed"]
    assert all(c["deterministic"] for c in r["cases"])
    # canonical hash stable across a second full run
    assert replay_all(ROOT)["corpus_hash"] == r["corpus_hash"]


def test_known_bad_case_fires_expected_rules():
    c = load_case(Path(ROOT) / "golden" / "terraform-public-bucket"
                  / "case.yaml")
    r = replay_case(c)
    assert r["verdict"] == "pass"
    assert r["violated"], "expected violations in a known-bad case"
    assert not r["false_negatives"]


def test_case_contract_rejects_bad_classification(tmp_path):
    d = tmp_path / "golden" / "x"
    d.mkdir(parents=True)
    (d / "case.yaml").write_text(yaml.safe_dump({
        "id": "x", "classification": "real-live", "tier": "golden",
        "task": "t", "scope": "s", "analyzers": ["k8s"],
        "expected_known_truth": {"violated_rules": ["PF-K8S-001"]}}))
    c = load_case(d / "case.yaml")
    # real-live is a valid classification, so this passes; bogus one fails
    assert case_errors(c) == []
    doc = yaml.safe_load((d / "case.yaml").read_text())
    doc["classification"] = "nope"
    (d / "case.yaml").write_text(yaml.safe_dump(doc))
    assert case_errors(load_case(d / "case.yaml"))


def test_validate_corpus():
    r = validate_corpus(ROOT)
    assert r["verdict"] == "pass" and not r["invalid"]
