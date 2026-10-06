"""Phase 8 gate: SLO budgets, OTel correlation, incident hypotheses, capacity."""

import json

import pytest

from platformforge.graph import GraphBuilder
from platformforge.observe import (SloContract, capacity, correlate,
                                   correlate_spans, error_budget)


def test_slo_contract_and_budget(tmp_path):
    c = SloContract.from_dict({"service": "payments", "sli": "avail",
                               "target": 99.9, "window": "30d"})
    assert c.window_seconds == 30 * 86400
    assert abs(c.allowed_error_ratio - 0.001) < 1e-9
    b = error_budget(c, total_events=1_000_000, bad_events=500)
    assert b["status"] == "ok" and b["burn_rate"] == 0.5
    assert b["budget"]["remaining_events"] == 500
    b2 = error_budget(c, total_events=1_000_000, bad_events=1200)
    assert b2["status"] == "exhausted" and b2["budget"]["remaining_events"] < 0
    b3 = error_budget(c)
    assert b3["status"] == "unresolved"
    with pytest.raises(ValueError):
        SloContract.from_dict({"service": "x", "sli": "y", "target": 99,
                               "window": "month"})


def test_otel_correlation(tmp_path):
    spans = tmp_path / "spans.jsonl"
    rows = [
        {"trace_id": "t1", "span_id": "s1", "service": "web", "name": "GET",
         "duration_ms": 100, "status": "ok"},
        {"trace_id": "t1", "span_id": "s2", "parent_span_id": "s1",
         "service": "api", "name": "handler", "duration_ms": 80,
         "status": "error"},
        {"trace_id": "t1", "span_id": "s3", "parent_span_id": "s2",
         "service": "db", "name": "query", "duration_ms": 60,
         "status": "ok"},
        {"trace_id": "t2", "span_id": "s9", "service": "web", "name": "GET",
         "duration_ms": 10, "status": "ok"},
    ]
    spans.write_text("\n".join(json.dumps(r) for r in rows))
    out = correlate_spans(spans)
    t1 = [t for t in out["traces"] if t["trace_id"] == "t1"][0]
    assert t1["error_services"] == ["api"]
    assert t1["critical_path_ms"] == 100 + 80 + 60
    assert out["service_summary"]["api"]["error_spans"] == 1


def test_incident_correlation():
    g = GraphBuilder()
    g.add_edge("service", "web", "service", "api", "calls")
    g.add_edge("service", "api", "database", "db", "depends_on")
    alerts = [{"service": "service/web", "at": 1000.0, "severity": "critical"}]
    changes = [{"target": "service/api", "at": 700.0, "kind": "deploy"},
               {"target": "service/web", "at": 900.0, "kind": "config"}]
    out = correlate(alerts, changes, graph=g.graph)
    hyps = out["incident_hypotheses"][0]["hypotheses"]
    assert hyps[0]["proximity"] == "self"  # config change on web itself
    assert any(h["proximity"].startswith("graph-depth") for h in hyps)
    assert "not causation" in out["incident_hypotheses"][0]["note"]


def test_capacity():
    out = capacity([
        {"resource": "cpu/node-a", "used": 96, "limit": 100},
        {"resource": "mem/node-b", "used": 50, "limit": 100},
        {"resource": "disk/node-c", "used": 88, "limit": 100},
        {"resource": "gpu/node-d", "used": 10, "limit": None},
    ])
    classes = {c["resource"]: c["class"] for c in out["capacity"]}
    assert classes == {"cpu/node-a": "saturated", "mem/node-b": "cool",
                       "disk/node-c": "hot", "gpu/node-d": "unresolved"}
    assert out["counts"] == {"items": 4, "hot": 2, "unresolved": 1}
