"""Phase B gates — temporal Graphfy: multi-layer edge evidence, graph
v1↔v2 compatibility/migration, event ledger, temporal queries.
"""

import json
import time
from pathlib import Path

import pytest

from platformforge.graph import persist
from platformforge.graph.events import EventLedger
from platformforge.graph.migrate import migrate_doc_v1_to_v2, migrate_graph
from platformforge.graph.model import SCHEMA, SCHEMA_V2, Edge, Graph, Node
from platformforge.graph.temporal import edge_first_seen, expire_stale_edges, graph_at, node_last_observed


def _g():
    g = Graph()
    g.add_node(Node("workload/a", "workload", "a"))
    g.add_node(Node("database/db", "database", "db"))
    return g


def test_edge_layers_preserve_declared_and_observed():
    g = _g()
    g.add_edge(Edge("workload/a", "database/db", "calls",
                    provenance="declared",
                    source_fact_ids=("f1",)))
    g.add_edge(Edge("workload/a", "database/db", "calls",
                    provenance="observed",
                    source_fact_ids=("f2",),
                    evidence=({"provenance": "observed",
                               "source_type": "otel",
                               "fact_ids": ["f2"],
                               "observed_at": "2025-01-01T00:00:00Z"},)))
    e = g.edges["workload/a->database/db:calls"]
    assert e.provenance == "observed"          # effective = strongest
    provs = {r["provenance"] for r in e.layers()}
    assert provs == {"declared", "observed"}   # declared evidence kept
    assert set(e.source_fact_ids) == {"f1", "f2"}


def test_layers_synthesized_for_v1_edges():
    e = Edge("a", "b", "calls", provenance="planned",
             source_fact_ids=("f9",))
    assert e.layers() == ({"provenance": "planned",
                          "fact_ids": ["f9"]},)


def test_temporal_merge_windows_and_samples():
    g = _g()
    g.add_edge(Edge("workload/a", "database/db", "calls",
                    provenance="observed",
                    temporal={"first_seen": "2025-01-01T00:00:00Z",
                              "last_seen": "2025-01-01T01:00:00Z",
                              "sample_count": 5}))
    g.add_edge(Edge("workload/a", "database/db", "calls",
                    provenance="observed",
                    temporal={"first_seen": "2025-01-01T02:00:00Z",
                              "last_seen": "2025-01-01T03:00:00Z",
                              "sample_count": 7}))
    t = g.edges["workload/a->database/db:calls"].temporal
    assert t["first_seen"] == "2025-01-01T00:00:00Z"
    assert t["last_seen"] == "2025-01-01T03:00:00Z"
    assert t["sample_count"] == 12


def test_v1_graph_serializes_as_v1_and_hashes_stable():
    g = _g()
    g.add_edge(Edge("workload/a", "database/db", "calls"))
    d = g.to_dict()
    assert d["schema"] == SCHEMA
    # v1 round-trip keeps identical hash (no silent evidence injection)
    assert Graph.from_dict(d).graph_hash == g.graph_hash


def test_v2_schema_emitted_only_when_layered():
    g = _g()
    g.add_edge(Edge("workload/a", "database/db", "calls",
                    evidence=({"provenance": "observed",
                               "fact_ids": ["f"]},)))
    assert g.to_dict()["schema"] == SCHEMA_V2
    # explicit downgrade strips layered fields
    assert g.to_dict(schema=SCHEMA)["schema"] == SCHEMA


def test_migrate_v1_to_v2_and_back():
    g = _g()
    g.add_edge(Edge("workload/a", "database/db", "calls",
                    provenance="declared", source_fact_ids=("f1",)))
    v1 = g.to_dict(schema=SCHEMA)
    v2 = migrate_doc_v1_to_v2(v1)
    assert v2["schema"] == SCHEMA_V2
    assert v2["migrated_from"] == SCHEMA
    rec = v2["edges"][0]["evidence"][0]
    assert rec["provenance"] == "declared" and rec["fact_ids"] == ["f1"]
    g2 = migrate_graph(Graph.from_dict(v1))
    assert g2.to_dict()["schema"] == SCHEMA_V2
    # v2 → back to v1 readable
    assert Graph.from_dict(
        g2.to_dict()).edges["workload/a->database/db:calls"].provenance \
        == "declared"


def test_from_dict_rejects_unknown_schema():
    with pytest.raises(ValueError):
        Graph.from_dict({"schema": "platformforge/graph/v99"})


def test_expire_stale_edges_marks_not_deletes():
    g = _g()
    g.add_edge(Edge("workload/a", "database/db", "calls",
                    provenance="observed",
                    temporal={"first_seen": "2025-01-01T00:00:00Z",
                              "last_seen": "2025-01-01T00:05:00Z",
                              "sample_count": 3}))
    out = expire_stale_edges(
        g, now="2025-01-02T00:00:00Z", max_age_s=3600)
    assert out == ["workload/a->database/db:calls"]
    e = g.edges["workload/a->database/db:calls"]
    assert e.temporal["expired"] is True  # marked, not removed


def test_event_ledger_append_query_compact(tmp_path):
    led = EventLedger(tmp_path)
    led.append({"kind": "observation", "timestamp": "2025-01-01T00:00:00Z",
                "node_ids": ["workload/a"]})
    led.append({"kind": "drift", "timestamp": "2025-01-02T00:00:00Z",
                "edge_id": "x->y:calls"})
    assert len(led.events()) == 2
    assert len(led.events(kind="drift")) == 1
    assert len(led.events(since="2025-01-02")) == 1
    marker = led.compact(snapshot_hash="abc", keep_after="2025-01-02")
    assert marker["removed_segments"] == ["2025-01-01.jsonl"]
    # compact marker itself is journaled
    assert any(e["kind"] == "snapshot" for e in led.events())


def test_event_ledger_prune_rescues_protected(tmp_path):
    led = EventLedger(tmp_path)
    old = {"kind": "observation", "timestamp": "2020-01-01T00:00:00Z",
           "fact_ids": ["prot-fact"]}
    led.append(old)
    led.append({"kind": "drift", "timestamp": "2020-01-01T01:00:00Z",
                "fact_ids": ["free"]})
    res = led.prune(keep_days=1, protected_ids={"prot-fact"})
    assert res["segments_dropped"] == 1
    assert res["events_rescued"] == 1
    rescued = list(tmp_path.glob(".platformforge/events/*.rescued.jsonl"))
    assert rescued and "prot-fact" in rescued[0].read_text()


def test_temporal_queries(tmp_path):
    g = _g()
    persist.save(g, tmp_path, source_type="observed")
    led = EventLedger(tmp_path)
    led.append({"kind": "observation",
                "timestamp": "2025-01-01T00:00:00Z",
                "edge_id": "workload/a->database/db:calls",
                "node_ids": ["workload/a"]})
    assert edge_first_seen(
        tmp_path, "workload/a->database/db:calls") == \
        "2025-01-01T00:00:00Z"
    assert node_last_observed(tmp_path, "workload/a") == \
        "2025-01-01T00:00:00Z"
    future = time.strftime("%Y-%m-%dT%H:%M:%SZ",
                           time.gmtime(time.time() + 3600))
    assert graph_at(tmp_path, future) is not None
    assert graph_at(tmp_path, "1970-01-01T00:00:00Z") is None


def test_v2_contract_doc_round_trip():
    doc = json.loads(
        Path("contracts/graph-v2.schema.json").read_text())
    assert doc["$id"] == SCHEMA_V2
