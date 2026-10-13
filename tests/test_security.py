"""Phase 10 gate: IAM graph, secret scan, SBOM, supply chain."""

import json

from platformforge.graph import GraphBuilder
from platformforge.models import Fact
from platformforge.rules import RuleEngine, load_catalog
from platformforge.security import analyze_iam_policy, analyze_sbom, analyze_supply, scan_secrets

POLICY = {"Version": "2012-10-17", "Statement": [
    {"Effect": "Allow", "Action": "*", "Resource": "*",
     "Principal": {"AWS": "arn:aws:iam::111:role/admin"}},
    {"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*",
     "Principal": "*"},
    {"Effect": "Allow", "Action": "sts:AssumeRole",
     "Resource": "arn:aws:iam::222:role/deploy",
     "Principal": {"AWS": "arn:aws:iam::111:role/ci"}},
]}

CYCLONE = {"bomFormat": "CycloneDX", "specVersion": "1.5",
           "components": [
               {"name": "openssl", "version": "3.0.0", "type": "library",
                "licenses": [{"license": {"id": "Apache-2.0"}}]},
               {"name": "libx", "version": "1.0", "type": "library",
                "licenses": []}]}

SUPPLY = {"artifacts": [
    {"image": "registry/app@sha256:" + "a" * 64, "signed": True,
     "slsa_provenance": True},
    {"image": "registry/app:latest", "signed": False}]}


def test_iam(tmp_path):
    p = tmp_path / "policy.json"
    p.write_text(json.dumps(POLICY))
    f = analyze_iam_policy(p)["facts"][0]
    a = f["attrs"]
    assert a["admin_grant"] and a["public_principals"] == 1
    assert a["wildcard_resources"] == 2 and a["wildcard_actions"] == 1
    g = GraphBuilder().from_facts([f]).graph
    kinds = {e.kind for e in g.edges.values()}
    assert "can_access" in kinds and "assumes" in kinds


def test_secret_scan_never_emits_values(tmp_path):
    (tmp_path / "app.env").write_text(
        "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE\npassword = hunter2\n")
    doc = scan_secrets(tmp_path)
    assert doc["counts"]["hits"] >= 1
    assert "AKIAIOSFODNN7EXAMPLE" not in json.dumps(doc)
    assert "hunter2" not in json.dumps(doc)


def test_secret_scan_prose_is_not_a_leak(tmp_path):
    """RW-5: prose mentioning passwords must emit zero secret_leak facts;
    a real-shaped secret in the same tree must still be found."""
    (tmp_path / "policy-notes.md").write_text(
        "The password policy: refuse and route on failure.\n"
        "pass: the token gate requires rotation every quarter.\n"
        "db_pass: check the runbook before restart.\n")
    doc = scan_secrets(tmp_path)
    assert doc["counts"]["hits"] == 0, doc["counts"]
    assert not [f for f in doc["facts"]
                if f["kind"] == "security.secret_leak"]
    (tmp_path / "app.env").write_text('DB_PASSWORD="hunter2!X9real"\n')
    doc = scan_secrets(tmp_path)
    leaks = [f for f in doc["facts"]
             if f["kind"] == "security.secret_leak"]
    assert len(leaks) == 1
    assert "hunter2" not in json.dumps(doc)


def test_sbom(tmp_path):
    p = tmp_path / "sbom.json"
    p.write_text(json.dumps(CYCLONE))
    f = analyze_sbom(p, vuln_db={"openssl@3.0.0": ["CVE-2024-0001"]})
    a = f["facts"][0]["attrs"]
    assert a["format"] == "cyclonedx" and a["component_count"] == 2
    assert a["vuln_count"] == 1 and a["unlicensed_components"] == ["libx"]


def test_supply(tmp_path):
    p = tmp_path / "supply.json"
    p.write_text(json.dumps(SUPPLY))
    doc = analyze_supply(p)
    pinned = {f["attrs"]["image"]: f["attrs"]["digest_pinned"]
              for f in doc["facts"]}
    assert list(pinned.values()) == [True, False]


def test_security_rules(tmp_path):
    p = tmp_path / "p.json"
    p.write_text(json.dumps(POLICY))
    s = tmp_path / "supply.json"
    s.write_text(json.dumps(SUPPLY))
    facts = [Fact.from_dict(x)
             for x in analyze_iam_policy(p)["facts"]
             + analyze_supply(s)["facts"]]
    rules = load_catalog(
        __import__("pathlib").Path(__file__).parents[1] / "rules/catalog")
    findings, _ = RuleEngine(rules).evaluate(facts)
    v = {f.rule_id for f in findings if f.status == "violated"}
    for rid in ("PF-SEC-001", "PF-SEC-002", "PF-SEC-003", "PF-SEC-030",
                "PF-SEC-031"):
        assert rid in v, rid
