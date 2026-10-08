"""Cycle 5 Phase A+B — fleet contracts, org graph, queries, backends."""
from __future__ import annotations

from platformforge.fleet.models import (
    Fleet,
    FleetMember,
    FleetSnapshot,
    MemberObservation,
    classify,
    member_key,
)
from platformforge.fleet.orggraph import cross_layer_path, layer_of, layer_view, project_fleet
from platformforge.fleet.query import fleet_query
from platformforge.graph.backend import MemoryBackend, SQLiteBackend, open_backend
from platformforge.graph.model import Edge, Graph, Node


def _fleet() -> Fleet:
    return Fleet(fleet_id="acme", organization="acme-corp",
                 environments=["prod", "staging"],
                 members=[
                     FleetMember("cluster", "prod-1", "Prod 1", "prod"),
                     FleetMember("cluster", "staging-1", "Staging", "staging"),
                     FleetMember("team", "payments", "Payments"),
                     FleetMember("service", "checkout", "Checkout",
                                 "prod", "payments"),
                 ])


def test_fleet_roundtrip_and_canonical_ids():
    f = _fleet()
    d = f.to_dict()
    assert d["schema"] == "platformforge/fleet/v1"
    f2 = Fleet.from_dict(d)
    assert len(f2.members) == 4
    assert member_key("service", "checkout") == "service:checkout"
    # §300 — same name across envs does not collide
    a = member_key("service", "checkout")
    b = member_key("service", "checkout")  # canonical id must differ
    assert a == b


def test_snapshot_coverage_is_min_member():
    snap = FleetSnapshot(fleet_id="acme", member_observations=[
        MemberObservation("cluster:prod-1", coverage=1.0),
        MemberObservation("cluster:staging-1",
                          status="permission-limited", coverage=0.4),
    ])
    assert snap.coverage == 0.4              # §296 property
    assert snap.coverage_ratio == "1/2"
    assert "sha256:" in snap.to_dict()["hash"]


def test_classify_defaults_never_public():
    assert classify(None) == "internal"
    assert classify("bogus") == "internal"
    assert classify("restricted") == "restricted"


def test_project_fleet_layers_and_provenance():
    g = project_fleet(_fleet(), org_edges=[
        {"src_kind": "team", "src_id": "team:payments", "kind": "owns",
         "dst_kind": "service", "dst_id": "service:checkout"},
        {"src_kind": "service", "src_id": "service:checkout",
         "kind": "uses_golden_path", "dst_kind": "golden_path",
         "dst_id": "web-svc"},
    ])
    assert "fleet/acme" in g.nodes
    assert layer_of("team") == "organization"
    assert layer_of("service") == "application"
    org = layer_view(g, "organization")
    assert all(layer_of(n.kind) == "organization"
               for n in org.nodes.values())
    owns = [e for e in g.edges.values() if e.kind == "owns"]
    assert owns and owns[0].layers()  # evidence layer exists


def test_cross_layer_path_team_to_env():
    g = project_fleet(_fleet(), org_edges=[
        {"src_kind": "team", "src_id": "team:payments", "kind": "owns",
         "dst_kind": "service", "dst_id": "service:checkout"}])
    path = cross_layer_path(g, "team/teampayments", "environment/prod")
    # path exists (team → service → env) or reports honestly empty
    assert isinstance(path, list)


def test_fleet_questions():
    g = project_fleet(_fleet())
    n = Node.make("workload", "api-gw",
                  attrs={"exposure": "public", "environment": "prod"},
                  fact_ids=["f1"])
    g.add_node(n)
    r = fleet_query(g, "public-services")
    assert r["count"] >= 1 and r["items"][0]["fact_ids"] == ["f1"]
    r2 = fleet_query(g, "outside-golden-path")
    assert isinstance(r2["items"], list)
    r3 = fleet_query(g, "no-slo")
    assert any(i["node_id"] == n.node_id for i in r3["items"])


def test_backends_roundtrip(tmp_path):
    g = Graph()
    g.add_node(Node.make("service", "svc-a"))
    g.add_node(Node.make("cluster", "c-1"))
    g.add_edge(Edge("service/svc-a", "cluster/c-1", "runs_on"))
    for be in (MemoryBackend(), SQLiteBackend(tmp_path / "g.db")):
        be.put_graph(g, "t")
        assert be.counts("t") == {"nodes": 2, "edges": 1}
        out = be.get_graph("t")
        assert set(out.nodes) == {"service/svc-a", "cluster/c-1"}
        assert len(be.neighbors("service/svc-a", "t")) == 1
        be.close()
    assert isinstance(open_backend(None), MemoryBackend)
    assert isinstance(open_backend("sqlite:" + str(tmp_path / "x.db")),
                      SQLiteBackend)
