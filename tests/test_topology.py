"""Phase G gates — runtime topology: OTel/Hubble/EndpointSlice →
runtime edges, attr whitelist, temporal windows, behavior classes."""

from platformforge.live.topology import (
    classify_behavior,
    edges_from_endpointslices,
    edges_from_hubble,
    edges_from_otel,
    runtime_temporal,
)


def test_otel_resource_spans_extract_service_edges():
    doc = {"resourceSpans": [{
        "resource": {"attributes": [
            {"key": "service.name", "value": {"stringValue": "web"}},
            {"key": "service.namespace",
             "value": {"stringValue": "prod"}},
            {"key": "http.request.header.authorization",
             "value": {"stringValue": "Bearer x"}},
            {"key": "db.statement",
             "value": {"stringValue": "SELECT * FROM users"}}]},
        "scopeSpans": [{"spans": [{
            "attributes": [
                {"key": "peer.service",
                 "value": {"stringValue": "billing"}},
                {"key": "http.url",
                 "value": {"stringValue": "https://x/y?token=1"}}]}]}]}]}
    edges = edges_from_otel([doc])
    assert len(edges) == 1
    e = edges[0]
    assert e["src"] == "service/prod/web"
    assert e["dst"] == "service/billing"
    assert e["sample_count"] == 1 and e["source_type"] == "otel"
    # whitelisted extraction — no url/header/statement leakage
    assert "token" not in str(edges) and "SELECT" not in str(edges)


def test_otel_db_peer_maps_to_database():
    spans = [{"service": "api",
              "attrs": {"db.system": "postgresql", "db.name": "shop"}}]
    edges = edges_from_otel(spans)
    assert edges[0]["dst"] == "database/shop"
    assert edges[0]["kind"] == "calls"


def test_hubble_flows_aggregate_and_keep_verdicts():
    flows = [
        {"flow": {"source": {"pod_name": "web", "namespace": "prod"},
                  "destination": {"pod_name": "db", "namespace": "prod"},
                  "verdict": "FORWARDED",
                  "l4": {"TCP": {"destination_port": 5432}}},
         "time": "2025-01-01T00:00:00Z"},
        {"flow": {"source": {"pod_name": "web", "namespace": "prod"},
                  "destination": {"pod_name": "db", "namespace": "prod"},
                  "verdict": "DROPPED",
                  "l4": {"TCP": {"destination_port": 5432}}},
         "time": "2025-01-01T00:05:00Z"}]
    edges = edges_from_hubble(flows)
    assert len(edges) == 1
    e = edges[0]
    assert e["src"] == "pod/prod/web" and e["dst"] == "pod/prod/db"
    assert e["sample_count"] == 2
    assert e["attrs"]["verdicts"] == {"DROPPED": 1, "FORWARDED": 1}
    assert e["attrs"]["ports"] == [5432]
    assert e["first_seen"] == "2025-01-01T00:00:00Z"


def test_endpointslice_membership_edges():
    eps = [{"metadata": {"namespace": "prod",
                         "labels": {"kubernetes.io/service-name": "web"}},
            "endpoints": [{"targetRef": {"kind": "Pod", "name": "web-1",
                                        "namespace": "prod"}},
                          {"targetRef": {"kind": "Pod", "name": "web-2"}}]}]
    edges = edges_from_endpointslices(eps)
    assert len(edges) == 2
    assert edges[0]["dst"] == "service/prod/web"
    assert edges[0]["kind"] == "exposes"


def test_behavior_classification():
    rt = [{"src": "service/prod/web", "dst": "service/billing",
           "kind": "calls", "sample_count": 1}]
    out = classify_behavior(rt, {"service/prod/web->service/billing:calls"})
    assert out[0]["behavior"] == "declared-and-observed"
    out = classify_behavior(rt, set())
    assert out[0]["behavior"] == "observed-undeclared"
    out = classify_behavior(
        rt, {"service/prod/web->service/billing:calls"},
        window_fresh=False)
    assert out[0]["behavior"] == "declared-not-seen-in-window"


def test_runtime_temporal_window():
    t = runtime_temporal({"first_seen": "a", "last_seen": "b",
                          "sample_count": 7})
    assert t == {"first_seen": "a", "last_seen": "b",
                 "window_start": "a", "window_end": "b",
                 "sample_count": 7}


def test_apply_runtime_edges_layers_with_declared():
    from platformforge.graph.model import SCHEMA_V2, Edge, Graph, Node
    from platformforge.live.topology import apply_runtime_edges
    g = Graph()
    g.add_node(Node("service/prod/web", "service", "web"))
    g.add_node(Node("service/prod/billing", "service", "billing"))
    g.add_edge(Edge("service/prod/web", "service/prod/billing", "calls",
                    provenance="declared"))
    apply_runtime_edges(g, [{"src": "service/prod/web",
                             "dst": "service/prod/billing",
                             "kind": "calls", "source_type": "otel",
                             "sample_count": 5,
                             "last_seen": "2025-01-01T01:00:00Z"}])
    e = g.edges["service/prod/web->service/prod/billing:calls"]
    assert e.provenance == "observed"
    assert {r["provenance"] for r in e.layers()} == \
        {"declared", "observed"}
    assert e.temporal["sample_count"] == 5
    assert g.to_dict()["schema"] == SCHEMA_V2


def test_apply_runtime_edges_creates_missing_nodes():
    from platformforge.graph.model import Graph
    from platformforge.live.topology import apply_runtime_edges
    g = Graph()
    n = apply_runtime_edges(g, [{"src": "pod/p/web", "dst": "pod/p/db",
                                 "kind": "calls", "sample_count": 1}])
    assert n == 1 and "pod/p/web" in g.nodes
