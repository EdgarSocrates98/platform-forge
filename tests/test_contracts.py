"""Phase 16 gate: every emitted object validates against its contract."""

import json
from pathlib import Path

import jsonschema
import yaml

from platformforge import __version__
from platformforge.iac import analyze_hcl
from platformforge.models import Fact, Finding
from platformforge.observe.slo import SloContract

CONTRACTS = Path(__file__).resolve().parents[1] / "contracts"


def _schema(name: str) -> dict:
    return json.loads((CONTRACTS / f"{name}.schema.json").read_text())


def test_all_contracts_are_valid_drafts():
    for f in sorted(CONTRACTS.glob("*.schema.json")):
        s = json.loads(f.read_text())
        assert s["$id"].startswith("platformforge/"), f"{f.name} missing $id"
        jsonschema.Draft202012Validator.check_schema(s)


def test_analyzer_facts_validate_after_model_roundtrip(tmp_path):
    (tmp_path / "main.tf").write_text(
        'resource "aws_s3_bucket" "b" { bucket = "x" }\n')
    doc = analyze_hcl(str(tmp_path))
    schema = _schema("fact")
    assert doc["facts"], "no facts emitted"
    for raw in doc["facts"]:
        fact = Fact.from_dict({**raw, "observed": raw.get("observed", True)})
        jsonschema.validate(fact.to_dict(), schema)


def test_finding_validates():
    schema = _schema("finding")
    f = Finding(rule_id="PF-IAC-001", severity="high", status="violated",
                evidence=["PF-IAC-1"], title="t", message="m")
    jsonschema.validate(f.to_dict(), schema)


def test_slo_contract_validates(tmp_path):
    c = tmp_path / "slo.yaml"
    c.write_text(yaml.safe_dump({
        "service": "payments",
        "sli": "availability",
        "target": 99.9, "window": "30d"}))
    contract = SloContract.load(c)
    jsonschema.validate(
        {"service": contract.service, "sli": contract.sli,
         "target": contract.target, "window": contract.window,
         "burn_rate_alerts": contract.burn_rate_alerts},
        _schema("slo-contract"))


def test_version_pinned():
    assert __version__ == "0.1.0"
    import platformforge
    assert platformforge.__version__
