"""Wave H — FinOps v2, security v2 (Kyverno/SLSA/Cosign), IAM v2 +
identity paths, risk v2 unknowns, change review composition."""

from __future__ import annotations

import json
from pathlib import Path

from platformforge.finops.focus import FOCUS_REQUIRED_V1, validate_focus
from platformforge.finops.ingest import ingest_billing
from platformforge.finops.insights import anomalies, commitments, finops_report, forecast, idle_resources
from platformforge.finops.unit import unit_economics
from platformforge.risk.engine import assess_change
from platformforge.sandbox.review import review_change
from platformforge.security.cosign import analyze_cosign
from platformforge.security.iam import analyze_iam_policy
from platformforge.security.identity import compromise_blast, who_can_access, who_can_become
from platformforge.security.kyverno import analyze_kyverno
from platformforge.security.slsa import slsa_assess

# ---------- FOCUS ----------

def test_focus_validate_compliant():
    row = {c: "x" for c in FOCUS_REQUIRED_V1}
    out = validate_focus([row])
    assert out["focus_compliant"] is True
    assert out["rows_failing"] == 0


def test_focus_validate_never_claims_empty():
    assert validate_focus([])["focus_compliant"] is False
    out = validate_focus([{"BilledCost": 1.0}])
    assert out["focus_compliant"] is False
    assert "BilledCost" not in out["missing_columns"][0]["missing"]


# ---------- unit economics ----------

def test_unit_economics_missing_denominator_unresolved():
    facts = [{"kind": "finops.cost", "attrs": {"amount": 100.0}}]
    out = unit_economics(facts, {"request": 1000})
    assert out["unit_economics"]["request"]["status"] == "measured"
    assert out["unit_economics"]["request"]["cost_per"] == 0.1
    assert out["unit_economics"]["user"]["status"] == "unresolved"
    assert "user" in out["unresolved"]


def test_unit_economics_zero_denominator_unresolved():
    out = unit_economics([], {"request": 0})
    assert out["unit_economics"]["request"]["status"] == "unresolved"


# ---------- billing ingest ----------

def test_ingest_aws_cur(tmp_path: Path):
    p = tmp_path / "cur.csv"
    p.write_text("lineItem/ResourceId,lineItem/UnblendedCost,"
                 "product/ProductName,lineItem/CurrencyCode\n"
                 "i-123,42.5,AmazonEC2,USD\n")
    out = ingest_billing(p)
    assert out["format"] == "aws_cur"
    assert out["rows"][0]["amount"] == 42.5
    assert out["rows"][0]["resource"] == "i-123"


def test_ingest_gcp_billing_json(tmp_path: Path):
    p = tmp_path / "gcp.json"
    p.write_text(json.dumps([{"cost": "12.50", "project.id": "proj-a",
                              "usage": {"unit": "h"},
                              "service.description": "Compute Engine"}]))
    out = ingest_billing(p)
    assert out["format"] == "gcp_billing"
    assert out["rows"][0]["amount"] == 12.5


def test_ingest_opencost(tmp_path: Path):
    p = tmp_path / "oc.json"
    p.write_text(json.dumps({"data": [
        {"name": "ns/web", "totalCost": 7.25,
         "window": {"start": "2026-01-01"}}]}))
    out = ingest_billing(p)
    assert out["format"] == "opencost"
    assert out["rows"][0]["amount"] == 7.25


def test_ingest_unknown_format_unresolved(tmp_path: Path):
    p = tmp_path / "weird.json"
    p.write_text(json.dumps([{"foo": "bar"}]))
    out = ingest_billing(p)
    assert "unresolved" in out


# ---------- finops insights ----------

def _costs(n_periods=3):
    return [{"kind": "finops.cost",
             "attrs": {"resource": "r1", "amount": 10.0 * (i + 1),
                       "period": f"2026-0{i + 1}", "tags": {}}}
            for i in range(n_periods)]


def test_idle_unresolved_without_utilization():
    out = idle_resources(_costs())
    assert out["status"] == "unresolved"
    assert "unlock" in out


def test_idle_measured():
    out = idle_resources(_costs(), {"r1": 0.01})
    assert out["status"] == "measured"
    assert out["idle"][0]["resource"] == "r1"


def test_anomaly_detection():
    facts = _costs(4)
    facts[-1]["attrs"]["amount"] = 500.0
    out = anomalies(facts)
    assert any(a["resource"] == "r1" for a in out["anomalies"])


def test_forecast_needs_periods():
    assert forecast(_costs(2))["status"] == "unresolved"
    assert forecast(_costs(4))["status"] == "measured"


def test_commitments_unresolved_without_declaration():
    assert commitments(_costs())["status"] == "unresolved"
    out = commitments(_costs(), {"svc": 25.0})
    assert out["status"] == "measured" and out["coverage_ratio"] < 1


def test_report_all_dimensions():
    out = finops_report(_costs(4))
    for dim in ("idle", "rightsizing", "anomalies", "forecast",
                "commitments", "shared"):
        assert dim in out


# ---------- kyverno ----------

def test_kyverno_legacy_without_version_unresolved(tmp_path: Path):
    (tmp_path / "pol.yaml").write_text(
        "apiVersion: kyverno.io/v1\nkind: ClusterPolicy\n"
        "metadata: {name: require-labels}\n"
        "spec: {validationFailureAction: Enforce, rules: [{}]}\n")
    out = analyze_kyverno(tmp_path)
    assert out["facts"][0]["attrs"]["legacy_type"] is True
    assert any(u["capability"] == "kyverno-version-check"
               for u in out["unresolved"])


def test_kyverno_legacy_deprecated_with_version(tmp_path: Path):
    (tmp_path / "pol.yaml").write_text(
        "apiVersion: kyverno.io/v1\nkind: Policy\n"
        "metadata: {name: p}\nspec: {rules: []}\n")
    out = analyze_kyverno(tmp_path, kyverno_version="v1.14")
    assert out["facts"][0]["attrs"]["legacy_deprecated"] is True


def test_kyverno_cel_kind_not_flagged(tmp_path: Path):
    (tmp_path / "vp.yaml").write_text(
        "apiVersion: policies.kyverno.io/v1alpha1\n"
        "kind: ValidatingPolicy\nmetadata: {name: vp}\n"
        "spec: {validations: []}\n")
    out = analyze_kyverno(tmp_path)
    assert out["facts"][0]["attrs"]["cel_type"] is True
    assert not out["unresolved"]


# ---------- slsa ----------

def test_slsa_no_provenance_unresolved():
    out = slsa_assess(None)
    assert out["slsa_level"] is None and out["status"] == "unresolved"


def test_slsa_l1_met():
    prov = {"predicate": {"buildDefinition": {"externalParameters": {}}}}
    out = slsa_assess(prov)
    assert out["levels"]["L1"]["met"] is True
    assert out["slsa_level"] == "L1"
    assert out["levels"]["L2"]["met"] is False  # gaps named, not smoothed


def test_slsa_level_never_inferred():
    out = slsa_assess({"predicate": {}}, evidence={"signed": True})
    assert out["slsa_level"] in (None, "L1")


# ---------- cosign ----------

def test_cosign_claimed_not_verified(tmp_path: Path):
    bundle = {"verificationMaterial": {"tlogEntries": [{}]},
              "dsseEnvelope": {"payload": "x", "signatures": [{"sig": "s"}]},
              "signatures": [{"sig": "s"}]}
    p = tmp_path / "img.sigstore.json"
    p.write_text(json.dumps(bundle))
    out = analyze_cosign(p)
    f = out["facts"][0]["attrs"]
    assert f["claimed_signed"] is True
    assert f["verified"] is False          # NEVER true offline
    assert any(u["capability"] == "cosign-verify" for u in out["unresolved"])


def test_cosign_unsigned_doc_no_verify_unlock(tmp_path: Path):
    p = tmp_path / "att.json"
    p.write_text(json.dumps({"predicateType": "x", "_type": "in-toto"}))
    out = analyze_cosign(p)
    assert out["facts"][0]["attrs"]["attestation"] is True
    assert out["unresolved"] == []


# ---------- iam v2 ----------

def _write_policy(tmp_path: Path, doc: dict) -> Path:
    p = tmp_path / "policy.json"
    p.write_text(json.dumps(doc))
    return p


def test_iam_trust_policy_oidc(tmp_path: Path):
    p = _write_policy(tmp_path, {"Statement": [{
        "Effect": "Allow", "Action": "sts:AssumeRoleWithWebIdentity",
        "Principal": {"Federated": "arn:aws:iam::123:oidc-provider/gh"},
        "Resource": "arn:aws:iam::123:role/ci"}]})
    f = analyze_iam_policy(p)["facts"][0]["attrs"]
    assert f["policy_type"] == "trust"
    assert "arn:aws:iam::123:oidc-provider/gh" in f["federated_providers"]


def test_iam_role_chaining_edges(tmp_path: Path):
    p = _write_policy(tmp_path, {"Statement": [{
        "Effect": "Allow", "Action": "sts:AssumeRole",
        "Principal": {"AWS": "arn:aws:iam::123:user/ops"},
        "Resource": "arn:aws:iam::123:role/admin"}]})
    f = analyze_iam_policy(p)["facts"][0]["attrs"]
    assert "arn:aws:iam::123:role/admin" in f["assumable_roles"]
    kinds = {e["kind"] for e in f["graph"]["edges"]}
    assert "assumes" in kinds


def test_iam_scp_detected(tmp_path: Path):
    p = _write_policy(tmp_path, {
        "PolicyType": "SCP",
        "Statement": [{"Effect": "Deny", "Action": "*",
                       "Resource": "*"}]})
    f = analyze_iam_policy(p)["facts"][0]["attrs"]
    assert f["policy_type"] == "scp"


def test_iam_identity_policy_admin(tmp_path: Path):
    p = _write_policy(tmp_path, {"Statement": [{
        "Effect": "Allow", "Action": "*", "Resource": "*"}]})
    f = analyze_iam_policy(p)["facts"][0]["attrs"]
    assert f["policy_type"] == "identity"
    assert f["admin_grant"] is True


# ---------- identity paths ----------

def _graph_with_assume():
    from platformforge.graph import GraphBuilder
    facts = [{"fact_id": "f1", "kind": "security.iam_policy",
              "source": "x", "location": "p", "tier": 3,
              "attrs": {"graph": {
                  "nodes": [{"kind": "iam_principal", "label": "user/ops"},
                            {"kind": "role", "label": "role/admin"},
                            {"kind": "policy", "label": "s3-bucket"}],
                  "edges": [
                      {"src_kind": "iam_principal", "src": "user/ops",
                       "dst_kind": "role", "dst": "role/admin",
                       "kind": "assumes"},
                      {"src_kind": "role", "src": "role/admin",
                       "dst_kind": "policy", "dst": "s3-bucket",
                       "kind": "can_access"}]}}}]
    return GraphBuilder().from_facts(facts).graph


def test_who_can_become():
    g = _graph_with_assume()
    out = who_can_become(g, "role/admin")
    assert out["status"] == "measured"
    assert out["can_become"][0]["principal"] == "iam_principal/user/ops"


def test_who_can_access():
    g = _graph_with_assume()
    out = who_can_access(g, "s3-bucket")
    assert out["count"] >= 1


def test_no_path_is_named_not_zero_risk():
    g = _graph_with_assume()
    out = who_can_become(g, "role/ghost")
    assert out["status"] == "no-path-found"


def test_compromise_blast():
    g = _graph_with_assume()
    out = compromise_blast(g, "role/role/admin")
    assert "blast" in out


# ---------- risk v2 ----------

def test_risk_unknown_never_low():
    out = assess_change({})  # everything unresolved
    assert sorted(out["unresolved"]) == sorted(out["decomposition"])
    assert out["confidence"] == 0.0
    assert out["underreported"] is True


def test_risk_partial_confidence():
    out = assess_change({"blast_radius": 2, "production": True})
    assert 0 < out["confidence"] < 1
    assert "test_coverage" in out["unresolved"]


# ---------- change review ----------

def test_review_change_pipeline(tmp_path: Path):
    (tmp_path / "main.tf").write_text(
        'resource "aws_instance" "web" { instance_type = "t3.micro" }\n')
    out = review_change(str(tmp_path), files={
        "main.tf": 'resource "aws_instance" "web" {\n'
                   '  instance_type = "t3.micro"\n}\n'
                   'resource "aws_security_group" "open" {\n'
                   '  ingress { cidr_blocks = ["0.0.0.0/0"] }\n}\n'})
    rev = out["review"]
    for dim in ("diff", "graph", "blast_radius", "findings_delta",
                "risk", "recommended_validation"):
        assert dim in rev
    assert rev["risk"]["confidence"] <= 1.0
