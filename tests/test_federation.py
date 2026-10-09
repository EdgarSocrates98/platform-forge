"""Phase H gates — cluster registry + federated graph + coverage."""

from platformforge.graph.model import Edge, Graph, Node
from platformforge.live.federation import Cluster, ClusterRegistry, federate, federation_coverage


def _g(tag):
    g = Graph()
    g.add_node(Node(f"pod/{tag}/web", "pod", "web"))
    g.add_node(Node(f"pod/{tag}/db", "pod", "db"))
    g.add_edge(Edge(f"pod/{tag}/web", f"pod/{tag}/db", "calls",
                    provenance="observed",
                    temporal={"last_seen": "2025-01-01T00:00:00Z",
                              "sample_count": 3}))
    return g


def test_registry_roundtrip(tmp_path):
    r = ClusterRegistry(tmp_path)
    r.register(Cluster("prod-eks", provider="eks", account="1111",
                       region="us-east-1", context="prod",
                       environment="prod"))
    r.register(Cluster("dev-kind", provider="kind", context="kind-dev"))
    out = r.list()
    assert [c["cluster_id"] for c in out] == ["dev-kind", "prod-eks"]
    assert r.get("prod-eks")["region"] == "us-east-1"
    assert r.unregister("dev-kind") and len(r.list()) == 1


def test_federate_merges_and_stamps_cluster():
    fed = federate({"c2": _g("b"), "c1": _g("a")})
    assert len(fed.nodes) == 4 and len(fed.edges) == 2
    e = fed.edges["pod/a/web->pod/a/db:calls"]
    assert e.attrs["cluster"] == "c1"
    assert e.temporal["sample_count"] == 3


def test_federate_shared_nodes_union_evidence():
    g1, g2 = _g("a"), _g("a")
    g1.edges["pod/a/web->pod/a/db:calls"] = Edge(
        "pod/a/web", "pod/a/db", "calls", provenance="declared")
    fed = federate({"c1": g1, "c2": g2})
    e = fed.edges["pod/a/web->pod/a/db:calls"]
    assert e.provenance == "observed"
    assert {r["provenance"] for r in e.layers()} == {"declared", "observed"}


def test_federation_coverage_gaps(tmp_path):
    r = ClusterRegistry(tmp_path)
    r.register(Cluster("c1"))
    r.register(Cluster("c2"))
    r.register(Cluster("c3"))
    out = federation_coverage(r, ["c1", "c2", "rogue"])
    assert out["status"] == "partial"
    assert out["missing"] == ["c3"] and out["unregistered"] == ["rogue"]


def test_federation_coverage_complete():
    r = ClusterRegistry("/tmp/nonexistent-root-pf")
    out = federation_coverage(r, ["x"])
    # no registered missing → complete; 'x' surfaces as unregistered
    assert out["status"] == "complete"
    assert out["unregistered"] == ["x"]
