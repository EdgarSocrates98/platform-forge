"""Phase 5 gate: IaC — HCL, plan/state, drift, PF-IAC-* rules."""

import json

from platformforge.iac import analyze_hcl, analyze_plan, analyze_state, drift
from platformforge.models import Fact
from platformforge.rules import RuleEngine, load_catalog
from platformforge.graph import GraphBuilder

TF = """
resource "aws_s3_bucket" "data" {
  bucket = "acme-data"
  acl    = "public-read"
  tags   = { team = "data" }
}

resource "aws_security_group" "web" {
  name = "web"
  ingress {
    cidr_blocks = ["0.0.0.0/0"]
    from_port   = 443
    to_port     = 443
  }
}

resource "aws_db_instance" "main" {
  identifier     = "db1"
  engine         = "postgres"
  storage_encrypted = true
  depends_on     = [aws_s3_bucket.data]
}

module "vpc" {
  source = "./modules/vpc"
}
"""

PLAN = {"format_version": "1.2", "terraform_version": "1.9.0",
        "resource_changes": [
            {"address": "aws_db_instance.main", "type": "aws_db_instance",
             "name": "main",
             "change": {"actions": ["delete", "create"]}},
            {"address": "aws_s3_bucket.data", "type": "aws_s3_bucket",
             "name": "data", "change": {"actions": ["create"]}}]}

STATE = {"values": {"root_module": {"resources": [
    {"address": "aws_s3_bucket.data", "type": "aws_s3_bucket",
     "name": "data", "provider_name": "registry.terraform.io/hashicorp/aws",
     "instances": [{"attributes": {"bucket": "acme-data",
                                   "acl": "private"}}]}]}}}


def _write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text)
    return p


def test_hcl_facts_and_graph(tmp_path):
    f = _write(tmp_path, "main.tf", TF)
    doc = analyze_hcl(f)
    kinds = {x["kind"] for x in doc["facts"]}
    assert {"iac.resource", "iac.module"} <= kinds
    res = {x["attrs"]["address"]: x for x in doc["facts"]
           if x["kind"] == "iac.resource"}
    assert res["aws_db_instance.main"]["attrs"]["cloud"] == "aws"
    assert res["aws_s3_bucket.data"]["attrs"]["tags"] == {"team": "data"}
    g = GraphBuilder().from_facts(doc["facts"]).graph
    assert ("terraform_resource/aws_db_instance.main->terraform_resource/"
            "aws_s3_bucket.data:depends_on") in g.edges
    assert "terraform_module/vpc" in g.nodes


def test_plan_and_state(tmp_path):
    p = _write(tmp_path, "plan.json", json.dumps(PLAN))
    doc = analyze_plan(p)
    changes = {f["attrs"]["address"]: f["attrs"] for f in doc["facts"]}
    assert changes["aws_db_instance.main"]["replace"] is True
    assert doc["versions"]["terraform"] == "1.9.0"
    s = _write(tmp_path, "state.json", json.dumps(STATE))
    sdoc = analyze_state(s)
    assert sdoc["facts"][0]["attrs"]["values"]["acl"] == "private"


def test_drift(tmp_path):
    tf = _write(tmp_path, "m.tf", 'resource "aws_s3_bucket" "data" {\n'
                '  bucket = "acme-data"\n  acl = "private"\n}\n')
    s = _write(tmp_path, "st.json", json.dumps(STATE))
    out = drift(analyze_hcl(tf)["facts"], analyze_state(s)["facts"])
    r = out["resources"][0]
    assert r["status"] == "converged" or r["status"] == "unresolved"
    out2 = drift(analyze_hcl(_write(
        tmp_path, "m2.tf", 'resource "aws_s3_bucket" "data" {\n'
        '  bucket = "acme-data"\n  acl = "public-read"\n}\n'))["facts"],
        analyze_state(s)["facts"])
    assert out2["resources"][0]["status"] == "drifted"
    assert out2["resources"][0]["diffs"][0]["attr"] == "acl"


def test_iac_rules_fire(tmp_path):
    f = _write(tmp_path, "main.tf", TF)
    facts = [Fact.from_dict(x) for x in analyze_hcl(f)["facts"]]
    rules = load_catalog(
        __import__("pathlib").Path(__file__).parents[1] / "rules/catalog")
    findings, skipped = RuleEngine(rules).evaluate(facts)
    violated = {f.rule_id for f in findings if f.status == "violated"}
    assert "PF-IAC-001" in violated   # public bucket ACL
    assert "PF-IAC-002" in violated   # 0.0.0.0/0 ingress
    assert "PF-IAC-003" in violated   # untagged sg + db
    assert "PF-IAC-020" in violated   # module without version
    p = _write(tmp_path, "plan.json", json.dumps(PLAN))
    pfacts = [Fact.from_dict(x) for x in analyze_plan(p)["facts"]]
    findings2, _ = RuleEngine(rules).evaluate(pfacts)
    v2 = {f.rule_id for f in findings2 if f.status == "violated"}
    assert "PF-IAC-010" in v2 and "PF-IAC-011" in v2
