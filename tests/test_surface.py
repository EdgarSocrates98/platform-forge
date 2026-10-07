"""§7 surface verbs — collect, diagnose, plan, diff, drift, impact,
context, policy, security, reliability, correlate, integrate, evals,
lab chaos (§93)."""

import json
from pathlib import Path

from platformforge.collect import collect, detect_file
from platformforge.diagnose import diagnose
from platformforge.evals import run_all
from platformforge.graph import GraphBuilder
from platformforge.lab.chaos import chaos, run_scenario
from platformforge.plan import remediation_plan


def test_detect_file_k8s(tmp_path):
    f = tmp_path / "deploy.yaml"
    f.write_text("apiVersion: apps/v1\nkind: Deployment\nmetadata: {name: x}\n")
    assert detect_file(f) == "k8s"
    (tmp_path / "main.tf").write_text('resource "aws_s3_bucket" "b" {}')
    assert detect_file(tmp_path / "main.tf") == "iac"
    (tmp_path / "x.txt").write_text("noise")
    assert detect_file(tmp_path / "x.txt") is None


def test_collect_iam(tmp_path):
    (tmp_path / "policy.json").write_text(json.dumps({
        "Statement": [{"Effect": "Allow", "Principal": {"AWS": "*"},
                       "Action": "*", "Resource": "*"}]}))
    out = collect(tmp_path)
    assert "iam" in out["detected"]
    assert any(f["kind"] == "security.iam_policy" for f in out["facts"])
    # secrets baseline always runs — undetected files are reported, not lost
    assert out["undetected"] == []


def _graph():
    return GraphBuilder().from_facts([
        {"fact_id": "f1", "kind": "k8s.workload", "source": "s",
         "location": "a.yaml", "tier": 3,
         "attrs": {"graph": {
             "nodes": [{"kind": "workload", "label": "prod/api",
                        "attrs": {"env": "staging"}},
                       {"kind": "k8s_service", "label": "prod/svc"}],
             "edges": [{"src_kind": "k8s_service", "src": "prod/svc",
                        "dst_kind": "workload", "dst": "prod/api",
                        "kind": "routes_to"}]}}},
    ]).graph


def test_diagnose_composes():
    g = _graph()
    facts = [{"fact_id": "f1", "kind": "k8s.workload", "source": "s",
              "location": "a.yaml", "tier": 3,
              "attrs": {"graph": {"nodes": [{"kind": "workload",
                                             "label": "prod/api"}]}}}]
    findings = [{"rule_id": "PF-K8S-008", "status": "violated",
                 "severity": "high", "evidence": ["f1"]}]
    out = diagnose(g, "workload/prod/api", findings, facts)
    assert out["findings"][0]["rule_id"] == "PF-K8S-008"
    assert "k8s_service/prod/svc" in out["blast_radius"]["nodes"]
    assert "owner" in str(out["unresolved"])
    assert diagnose(g, "workload/none", [], [])["refusal"] == \
        "platform.diagnose.unknown_node"


def test_plan_orders_and_refuses():
    findings = [
        {"rule_id": "B", "status": "violated", "severity": "low",
         "evidence": ["e1"], "remediation": "fix b"},
        {"rule_id": "A", "status": "violated", "severity": "critical",
         "evidence": ["e2"], "remediation": "fix a"},
        {"rule_id": "C", "status": "violated", "evidence": []},
    ]
    out = remediation_plan(findings)
    assert out["steps"][0]["rule_id"] == "A"   # critical first
    assert out["refused"] == ["C"]


def test_chaos_simulation_and_prod_refusal():
    g = _graph()
    out = chaos(g, "pod_kill", "workload/prod/api")
    assert out["environment"] == "simulation"
    assert "k8s_service/prod/svc" in out["degraded_nodes"]
    # production nodes refused by default (§93)
    g2 = GraphBuilder().from_facts([
        {"fact_id": "f", "kind": "k8s.workload", "source": "s",
         "location": "a", "tier": 3,
         "attrs": {"graph": {"nodes": [{"kind": "workload",
                                       "label": "prod/db",
                                       "attrs": {"env": "production"}}],
                             "edges": []}}}]).graph
    out2 = chaos(g2, "node_unavailable", "workload/prod/db")
    assert out2["refusal"] == "platform.chaos.production_default"
    assert chaos(g, "bogus", "workload/prod/api")["refusal"]


def test_chaos_scenario_dir():
    d = Path("lab/chaos-pod-kill")
    if not d.is_dir():
        return
    out = run_scenario(d)
    assert out["fault"] == "pod_kill"
    assert out["impacted_total"] >= 1


def test_evals_corpus():
    out = run_all()
    assert out["evals"] >= 9
    assert out["counts"]["fail"] == 0
    types = {r["type"] for r in out["results"]}
    assert {"golden", "routing", "security", "contract",
            "token_economy", "graph_correctness",
            "property"} <= types
