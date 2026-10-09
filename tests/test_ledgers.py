"""FP/FN ledger contract — §64–§68."""
import yaml

from platformforge.cases.ledgers import (
    ROOT_CAUSES,
    FalseNegativeRecord,
    FalsePositiveRecord,
    ledger_report,
    record_errors,
    validate_ledgers,
)


def test_fp_record_contract():
    good = {"finding_id": "f1", "rule": "PF-K8S-001",
            "case": "k8s-bad-readiness", "why_false": "init container",
            "root_cause": "rule-too-broad",
            "regression_test": ".platformforge/cases/golden/k8s-bad-readiness"}
    assert record_errors(good, "fp") == []
    assert record_errors({**good, "why_false": ""}, "fp")
    assert record_errors({**good, "root_cause": "aliens"}, "fp")


def test_fn_record_contract():
    good = {"finding_id": "f2", "rule": "PF-SEC-001",
            "case": "aws-dump", "missed_evidence": "wildcard in policy",
            "root_cause": "missing-extractor",
            "regression_test": "lab/scenarios/aws-dump"}
    assert record_errors(good, "fn") == []
    assert record_errors({**good, "missed_evidence": ""}, "fn")


def test_dataclasses_serialize():
    fp = FalsePositiveRecord(finding_id="a", rule="r", case="c",
                             why_false="w", root_cause="bad-scope",
                             regression_test="tests/x.py")
    assert fp.to_dict()["schema"] == "platformforge/fp-record/v1"
    fn = FalseNegativeRecord(finding_id="b", rule="r", case="c",
                             missed_evidence="m",
                             root_cause="graph-gap", regression_test="t")
    assert fn.to_dict()["schema"] == "platformforge/fn-record/v1"


def test_root_cause_taxonomy_is_the_spec_set():
    assert len(ROOT_CAUSES) == 12
    assert "context-omission" in ROOT_CAUSES
    assert "provider-limitation" in ROOT_CAUSES


def test_empty_ledgers_are_valid_and_honest():
    r = ledger_report()
    assert r["verdict"] == "pass"
    # precision must not be claimed below the meaningful-sample floor
    # (no records at all, or fewer than 3 records to grade)
    assert r["precision"] in (None,) or r["precision"]["value"] is None
    assert validate_ledgers()["verdict"] == "pass"


def test_regression_selector_resolves_to_test_name():
    """FP-RW5-001 in the real ledger points at a ::test selector —
    the resolver must verify both file and function."""
    r = validate_ledgers()
    assert r["verdict"] == "pass", r["errors"]
    rep = ledger_report()
    assert rep["false_positives"] >= 1
    assert rep["precision"]["records"] == rep["false_positives"] + \
        rep["false_negatives"]


def test_regression_pointer_must_resolve(tmp_path):
    f = tmp_path / "false-positives.yaml"
    f.write_text(yaml.safe_dump({"records": [{
        "finding_id": "x", "rule": "r", "case": "c",
        "why_false": "w", "root_cause": "bad-scope",
        "regression_test": "nonexistent/path/xyz"}]}))
    r = validate_ledgers(tmp_path)
    assert r["verdict"] == "fail" and "regression_test" in r["errors"][0]
