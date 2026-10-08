

def test_focus_version_pinned_and_dataset_detection():
    """Polish wave2 — unknown spec versions refuse instead of
    'compliant'; 1.3/1.4 datasets are detected, not claimed."""
    from platformforge.finops.focus import FOCUS_KNOWN_VERSIONS, detect_datasets, validate_focus
    rows = [{"BilledCost": 1, "BillingAccountId": "a",
             "BillingPeriodStart": "x", "BillingPeriodEnd": "y",
             "ChargeCategory": "usage", "ChargeClass": "regular",
             "ChargePeriodStart": "x", "ChargePeriodEnd": "y",
             "Currency": "USD", "ServiceName": "s", "SkuId": "k",
             "ContractCommitmentId": "c1", "ContractId": "ct",
             "ContractCommitmentCost": 5}]
    r = validate_focus(rows, "1.4")
    assert r["focus_compliant"] and r["spec_version"] == "1.4"
    assert "contract-commitment" in r["datasets_detected"]
    assert "cost-and-usage" in detect_datasets(rows)
    bad = validate_focus(rows, "99.9")
    assert bad["refusal"] == "PF-FINOPS-FOCUS-VERSION"
    assert bad["focus_compliant"] is False
    assert "1.4" in FOCUS_KNOWN_VERSIONS
