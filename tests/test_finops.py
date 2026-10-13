"""Phase 9 gate: cost facts, allocation, FOCUS projection, graph costing."""

import json

from platformforge.finops import allocate, cost_facts, cost_summary, graph_cost, to_focus
from platformforge.graph import GraphBuilder

ROWS = [
    {"resource": "db/prod", "service": "rds", "amount": 120.0,
     "currency": "USD", "period": "2026-09",
     "tags": {"cost_center": "payments"}},
    {"resource": "cache/prod", "service": "elasticache", "amount": 40.0,
     "currency": "USD", "period": "2026-09", "tags": {}},
    {"resource": "lb/prod", "service": "elb", "amount": 25.0,
     "currency": "USD", "period": "2026-09",
     "tags": {"cost_center": "checkout"}},
    {"resource": "incomplete-row"},  # skipped
]


def _facts(tmp_path):
    p = tmp_path / "costs.json"
    p.write_text(json.dumps(ROWS))
    return cost_facts(p)["facts"]


def test_cost_facts_and_summary(tmp_path):
    facts = _facts(tmp_path)
    assert len(facts) == 3
    s = cost_summary(facts)
    assert s["total"] == 185.0
    assert s["by_period"]["2026-09"]["rds"] == 120.0


def test_allocate(tmp_path):
    out = allocate(_facts(tmp_path), by="cost_center")
    assert out["allocation"]["payments"] == 120.0
    assert out["unallocated_resources"] == ["cache/prod"]
    assert abs(out["shares"]["payments"] - 120 / 185) < 1e-3


def test_focus_projection(tmp_path):
    out = to_focus(ROWS[:1])
    row = out["focus_rows"][0]
    assert row["BilledCost"] == 120.0 and row["ResourceId"] == "db/prod"
    assert row["ServiceName"] == "rds"


def test_graph_cost(tmp_path):
    b = GraphBuilder()
    b.add_edge("workload", "pay", "cost_center", "payments", "billed_to")
    b.add_edge("workload", "pay", "database", "db-prod", "depends_on")
    facts = _facts(tmp_path)
    # cost resource names must match node ids or suffixes
    out = graph_cost(b.graph, facts)
    assert out["unattributed_resources"]  # no billed_to on db/prod nodes
    assert "payments" not in out["per_cost_center"]  # resource ids differ
    assert out["unresolved"] is True
