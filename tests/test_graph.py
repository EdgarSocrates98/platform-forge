"""Phase 4 gate: Graphfy — provenanced graph, queries, blast radius, diff."""

import json

import jsonschema

from platformforge.graph import (
    Graph,
    GraphBuilder,
    blast_radius,
    cycles,
    dependencies,
    dependents,
    diff,
    gaps,
    load,
    paths,
    save,
    snapshots,
)


def _facts():
    return [
        {"fact_id": "F1", "kind": "k8s.workload", "tier": "t2",
         "attrs": {"graph": {
             "nodes": [{"kind": "workload", "label": "payments"},
                       {"kind": "workload", "label": "checkout"}],
             "edges": [{"src_kind": "workload", "src": "checkout",
                        "dst_kind": "workload", "dst": "payments",
                        "kind": "calls"}]}}},
        {"fact_id": "F2", "kind": "k8s.secret_ref", "tier": "t2",
         "attrs": {"graph": {
             "nodes": [{"kind": "secret", "label": "db-creds"}],
             "edges": [{"src_kind": "workload", "src": "payments",
                        "dst_kind": "secret", "dst": "db-creds",
                        "kind": "uses_secret"}]}}},
        {"fact_id": "F3", "kind": "team.ownership", "tier": "t6",
         "attrs": {"graph": {
             "nodes": [{"kind": "team", "label": "pay-team"}],
             "edges": [{"src_kind": "team", "src": "pay-team",
                        "dst_kind": "workload", "dst": "payments",
                        "kind": "owns"}]}}},
    ]


def _graph() -> Graph:
    return GraphBuilder().from_facts(_facts()).graph


def test_build_from_facts_provenance(tmp_path):
    g = _graph()
    assert set(g.nodes) == {"workload/payments", "workload/checkout",
                            "secret/db-creds", "team/pay-team"}
    e = g.edges["team/pay-team->workload/payments:owns"]
    assert e.provenance == "inferred"  # t6 fact (llm-inference)
    e2 = g.edges["workload/payments->secret/db-creds:uses_secret"]
    assert e2.provenance == "planned" and e2.source_fact_ids == ("F2",)
    schema_path = (__import__("pathlib").Path(__file__).parents[1]
                   / "contracts/graph.schema.json")
    jsonschema.validate(g.to_dict(), json.loads(schema_path.read_text()))


def test_queries(tmp_path):
    g = _graph()
    assert dependencies(g, "workload/checkout") == {
        "workload/payments": 1, "secret/db-creds": 2}
    assert dependents(g, "secret/db-creds") == {"workload/payments": 1,
                                                "workload/checkout": 2}
    p = paths(g, "workload/checkout", "secret/db-creds")
    assert p == [["workload/checkout", "workload/payments",
                  "secret/db-creds"]]
    assert cycles(g) == []


def test_blast_radius_classes(tmp_path):
    g = _graph()
    br = blast_radius(g, "secret/db-creds")
    assert br["impacted_total"] == 2
    assert br["by_class"]["security"] == ["workload/payments"]
    assert br["by_class"]["runtime"] == ["workload/checkout"]
    assert "not proven causality" in br["note"]


def test_gaps_and_cycles(tmp_path):
    g = _graph()
    gp = gaps(g)
    assert "workload/checkout" in gp["ownership_gaps"]
    assert "workload/payments" not in gp["ownership_gaps"]  # owned by team
    assert set(gp["unmonitored"]) == {"workload/checkout", "workload/payments"}
    b = GraphBuilder()
    b.add_edge("service", "a", "service", "b", "depends_on")
    b.add_edge("service", "b", "service", "a", "depends_on")
    assert cycles(b.graph) == [["service/a", "service/b", "service/a"]]


def test_persist_and_diff(tmp_path):
    g = _graph()
    save(g, tmp_path)
    assert load(tmp_path).graph_hash == g.graph_hash
    assert snapshots(tmp_path)[0]["graph_hash"] == g.graph_hash
    g2 = GraphBuilder().from_facts(_facts() + [{
        "fact_id": "F4", "kind": "exposure", "tier": "t2",
        "attrs": {"graph": {
            "edges": [{"src_kind": "workload", "src": "payments",
                       "dst_kind": "api", "dst": "public",
                       "kind": "exposes"}]}}}]).graph
    d = diff(g, g2)
    assert "workload/payments->api/public:exposes" in d["edges_added"]
    assert d["security_changed"] is True
    assert d["hash_before"] != d["hash_after"]


def test_build_view_snapshot(tmp_path):
    """`graph view --snapshot` emits the named snapshot, stamped."""
    from platformforge import graphview

    g = _graph()
    save(g, tmp_path)
    view = graphview.build_view(tmp_path, snapshot=g.graph_hash)
    assert view is not None
    assert view.descriptor.snapshot_id == g.graph_hash
    assert view.descriptor.node_count == len(g.nodes)
    # latest view carries no snapshot stamp
    assert graphview.build_view(tmp_path).descriptor.snapshot_id == ""
    # missing snapshot fails closed
    assert graphview.build_view(tmp_path, snapshot="deadbeef") is None


def test_paths_bounded_on_dense_unreachable(tmp_path):
    """freeze dogfood: DFS wandered minutes on dense graphs when dst was
    deep/unreachable — BFS + expansion cap must terminate fast."""
    import time

    from platformforge.graph.bench import synthetic_graph
    g = synthetic_graph(5_000)
    t0 = time.time()
    out = paths(g, "service/svc-0", "service/svc-5")
    assert time.time() - t0 < 30
    assert isinstance(out, list)


def test_diff_identical_structure_skips_gap_sweeps(monkeypatch):
    """freeze dogfood: gaps() ran Tarjan + sweeps even on no-op diffs.
    Identical structure must report all flags false with empty deltas
    without calling gaps() at all."""
    import importlib
    dmod = importlib.import_module("platformforge.graph.diff")

    g = _graph()
    called = []
    monkeypatch.setattr(dmod, "gaps",
                        lambda gr: called.append(gr) or gaps(gr))
    d = diff(g, g)
    assert called == []
    for key in ("external_exposure", "ownership_gaps", "unmonitored",
                "unprotected", "unallocated_cost"):
        assert d["gap_deltas"][key + "_changed"] is False
        assert d["gap_deltas"][key + "_delta"] == {"added": [],
                                                 "removed": []}
    assert d["security_changed"] is False
    assert d["hash_before"] == d["hash_after"]
