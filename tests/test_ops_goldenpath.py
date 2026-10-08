"""Phase P/Q gates — golden-path lifecycle + cost/security gates."""

from platformforge.ops.gates import CostDelta, gate_network_exposure, gate_vulnerabilities, security_gates
from platformforge.ops.goldenpath import PlatformRequest, readiness_score, validate_request


def _req():
    return PlatformRequest(request_id="r1", requester="ada",
                           team="checkout", kind="service",
                           template="python-svc", params={"name": "api"},
                           environment="dev")


def _receipt(kind):
    return {"kind": kind}


def test_request_walks_full_lifecycle():
    r = _req()
    assert r.transition("validated", receipt=_receipt("validation"))["ok"]
    assert r.transition("planned", receipt=_receipt("plan"))["ok"]
    assert r.transition("policy-reviewed",
                        receipt=_receipt("policy-decision"))["ok"]
    # approved requires policy + cost + security + approval receipts
    r.receipts += [_receipt("cost-estimate"), _receipt("security-review"),
                   _receipt("approval")]
    assert r.transition("approved")["ok"]
    assert r.transition("provisioned",
                        receipt=_receipt("execution"))["ok"]
    assert r.transition("observed",
                        receipt=_receipt("observation"))["ok"]
    assert r.transition("scored", receipt=_receipt("scorecard"))["ok"]
    assert r.transition("decommissioned")["ok"]
    assert r.state == "decommissioned"


def test_transition_without_receipt_refused():
    r = _req()
    r.transition("validated", receipt=_receipt("validation"))
    r.transition("planned", receipt=_receipt("plan"))
    # no policy-decision receipt → policy-reviewed refused
    r3 = r.transition("approved")
    assert r3["refusal"] == "PF-OPS-REQ-BAD-TRANSITION"
    r4 = r.transition("policy-reviewed")
    assert r4["refusal"] == "PF-OPS-REQ-MISSING-RECEIPT"


def test_bad_transition_refused():
    r = _req()
    out = r.transition("approved")
    assert out["refusal"] == "PF-OPS-REQ-BAD-TRANSITION"


def test_validate_request_missing_inputs():
    r = _req()
    r.params = {}
    tpl = {"python-svc": {"inputs": [{"name": "name",
                                      "required": True}]}}
    v = validate_request(r, tpl)
    assert not v["ok"]
    assert any(f["refusal"] == "PF-OPS-REQ-MISSING-INPUT"
               for f in v["findings"])


def test_validate_unknown_template():
    r = _req()
    r.template = "nonexistent"
    v = validate_request(r, {})
    assert any(f["refusal"] == "PF-OPS-REQ-UNKNOWN-TEMPLATE"
               for f in v["findings"])


def test_readiness_unknown_is_not_ready():
    card = {"axes": {"security": {"grade": "unknown"},
                     "reliability": {"grade": "A"}}}
    s = readiness_score(card)
    assert s["verdict"] == "not-ready"
    assert "security" in s["unknown_axes"]


def test_readiness_all_A_ready():
    card = {"axes": {a: {"grade": "A"} for a in
                     ("security", "reliability", "cost")}}
    assert readiness_score(card)["verdict"] == "ready"


def test_cost_delta_gate():
    cd = CostDelta(current_monthly=100, planned_monthly=140,
                   basis="unit-price", confidence="medium",
                   source="finops-db")
    assert cd.delta == 40.0
    assert cd.gate(budget_increase_max=50)["status"] == "pass"
    assert cd.gate(budget_increase_max=30)["status"] == "fail"
    assert cd.gate(increase_pct_max=30)["status"] == "fail"


def test_no_estimate_is_unknown():
    cd = CostDelta()
    assert cd.delta is None
    assert cd.gate(budget_increase_max=10)["status"] == "unknown"


def test_exposure_gate_catches_public():
    g = gate_network_exposure(
        {"adds": {"network": [{"cidr": "0.0.0.0/0",
                               "port": 22}]}})
    assert g["status"] == "fail"
    g2 = gate_network_exposure({"adds": {"network": [
        {"cidr": "10.0.0.0/8"}]}})
    assert g2["status"] == "pass"


def test_vuln_gate_no_scan_unknown():
    assert gate_vulnerabilities(None)["status"] == "unknown"
    g = gate_vulnerabilities({"new_findings": [
        {"id": "CVE-1", "severity": "critical"}]})
    assert g["status"] == "fail"


def test_security_verdict_worst_wins():
    out = security_gates(
        diff={"adds": {"network": [{"cidr": "10.0.0.0/8"}]}},
        ctx={}, vuln_scan=None)
    assert out["verdict"] == "unknown"   # vuln gate unknown → verdict
