"""Cycle 2 Phase G — prometheus/grafana/semconv/postmortem/dr/slo-burn."""
from __future__ import annotations

import json

from platformforge.observe import (
    SloContract,
    analyze_grafana,
    analyze_prometheus,
    analyze_semconv,
    dr_model,
    multi_window_burn,
    postmortem,
    timeline,
)


def test_prometheus_rules_and_export(tmp_path):
    (tmp_path / "rules.yaml").write_text(
        "groups:\n- name: svc\n  rules:\n  - alert: HighErr\n"
        "    expr: 'rate(err{service=\"api\"}[5m]) > 0.1'\n"
        "    labels: {severity: page}\n"
        "  - record: job:rate5m\n    expr: 'rate(req[5m])'\n")
    (tmp_path / "q.json").write_text(json.dumps({
        "status": "success",
        "data": {"resultType": "vector",
                 "result": [{"metric": {"__name__": "up"}, "value": [1, "1"]}]}}))
    out = analyze_prometheus(tmp_path)
    kinds = {f["kind"] for f in out["facts"]}
    assert {"prometheus.alert", "prometheus.recording",
            "prometheus.series"} <= kinds
    series = next(f for f in out["facts"]
                  if f["kind"] == "prometheus.series")
    assert series["tier"] == 1  # measured, not declared
    alert = next(f for f in out["facts"]
                 if f["kind"] == "prometheus.alert")
    assert alert["attrs"]["service_refs"] == ["api"]
    assert alert["attrs"]["severity"] == "page"


def test_grafana_observes(tmp_path):
    (tmp_path / "dash.json").write_text(json.dumps({
        "title": "API Overview", "uid": "api1",
        "panels": [{"type": "graph", "targets":
                    [{"expr": 'rate(req{service="api"}[5m])'}]},
                   {"type": "row", "panels":
                    [{"targets": [{"expr": 'lag{service="worker"}'}]}]}]}))
    out = analyze_grafana(tmp_path)
    d = out["facts"][0]
    assert d["attrs"]["services"] == ["api", "worker"]
    edges = d["attrs"]["graph"]["edges"]
    assert all(e["kind"] == "observed_by" for e in edges)


def test_semconv_edges(tmp_path):
    (tmp_path / "spans.jsonl").write_text(
        json.dumps({"trace_id": "t1", "span_id": "s1",
                    "resource": {"service.name": "api",
                                 "k8s.deployment.name": "api-dep",
                                 "k8s.namespace.name": "prod"}}) + "\n")
    out = analyze_semconv(tmp_path / "spans.jsonl")
    f = out["facts"][0]
    assert f["attrs"]["semconv"]["k8s.deployment.name"] == "api-dep"
    assert f["attrs"]["graph"]["edges"][0]["kind"] == "runs_on"


def test_multi_window_burn():
    c = SloContract.from_dict({"service": "api", "sli": "ok",
                               "target": 99.9, "window": "30d"})
    out = multi_window_burn(c, {
        "1h": {"good_events": 990, "bad_events": 5},   # burn ~5 → firing
        "6h": {"good_events": 9990, "bad_events": 5},  # burn ~0.5 → ok
        "3d": {}})
    assert out["windows"]["1h"]["status"] == "firing"
    assert out["windows"]["6h"]["status"] == "ok"
    assert out["windows"]["3d"]["status"] == "unresolved"
    assert out["firing_windows"] == ["1h"]


def test_postmortem_never_invents_root_cause():
    pm = postmortem({"title": "x", "hypotheses": [
        {"change": "deploy-1", "causality": "correlated"},
        {"change": "deploy-2", "causality": "candidate"}]})
    assert pm["postmortem"]["root_cause"]["status"] == "unresolved"


def test_timeline_sorted():
    t = timeline([{"at": 30, "kind": "alert"}, {"at": 10, "kind": "change"},
                  {"at": 20, "kind": "log"}])
    assert [e["kind"] for e in t["timeline"]] == ["change", "log", "alert"]


def test_dr_backup_not_restore():
    facts = [
        {"fact_id": "PF-A", "kind": "cloud.aws.db",
         "location": "db1",
         "attrs": {"resource_type": "database", "name": "db1",
                   "backup_retention": 7}},
        {"fact_id": "PF-B", "kind": "cloud.aws.db",
         "location": "db2",
         "attrs": {"resource_type": "database", "name": "db2",
                   "backup_retention": 7, "restore_tested": True}},
    ]
    out = dr_model(facts)
    d1 = next(r for r in out["dr"] if r["resource"] == "db1")
    d2 = next(r for r in out["dr"] if r["resource"] == "db2")
    assert d1["protection"] == "unresolved"   # declared ≠ proven
    assert d2["protection"] == "evidenced"
