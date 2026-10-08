"""Cycle 4 phase R — operational Graphfy projection.

Projects an Operation + its ExecutionEnvelope + approvals into graph
nodes/edges. Operational edges carry provenance=observed, a
`layer="operation"` evidence record, and cite the ledger receipt/event
hashes — execution history stays queryable but separable from the
platform dependency graph (kind-prefix `operation:` on the layer).
"""

from __future__ import annotations

from typing import Any

from platformforge.graph.model import Edge, Graph, Node

LAYER = "operation"


def _node(kind: str, label: str, attrs: dict[str, Any] | None = None,
          fact_ids=()) -> Node:
    return Node.make(kind, label, attrs, fact_ids)


def project_operation(op, envelope=None,
                      approvals: list | None = None,
                      ledger=None) -> dict[str, list]:
    """Build nodes+edges for one operation. `op` is an Operation;
    `envelope` an ExecutionEnvelope or None; `approvals` Approval
    objects; `ledger` an OperationLedger for receipt citations."""
    nodes: list[Node] = []
    edges: list[Edge] = []
    receipts = [e.entry_hash for e in
                (ledger.entries if ledger else [])]

    op_node = _node("operation", op.operation_id,
                    {"state": op.state, "actor": op.actor})
    nodes.append(op_node)

    intent_node = _node("change_intent", getattr(op, "intent_id", "")
                        or (envelope.intent_id if envelope else "unknown"))
    nodes.append(intent_node)
    edges.append(Edge(op_node.node_id, intent_node.node_id, "intends",
                      provenance="observed",
                      evidence=({"provenance": "observed",
                                 "layer": LAYER,
                                 "receipt_ids": receipts[-5:]},)))

    if envelope is not None:
        env_node = _node("execution_envelope", envelope.execution_id,
                         {"executor": envelope.executor,
                          "hash": envelope.hash()})
        nodes.append(env_node)
        edges.append(Edge(op_node.node_id, env_node.node_id,
                          "executed_by", provenance="observed",
                          evidence=({"provenance": "observed",
                                    "layer": LAYER,
                                    "receipt_ids": receipts[-3:]},)))
        for res in envelope.scope:
            res_node = _node("workload", res)
            nodes.append(res_node)
            edges.append(Edge(env_node.node_id, res_node.node_id,
                              "mutates", provenance="planned",
                              confidence=0.9,
                              evidence=({"provenance": "planned",
                                         "layer": LAYER,
                                         "envelope_hash":
                                             envelope.hash()},)))

    for ap in approvals or []:
        ap_node = _node("approval", ap.approval_id,
                        {"actor": ap.actor, "role": ap.role,
                         "type": ap.type})
        nodes.append(ap_node)
        edges.append(Edge(op_node.node_id, ap_node.node_id,
                          "approved_by", provenance="observed",
                          evidence=({"provenance": "observed",
                                    "layer": LAYER,
                                    "subject_hash": ap.subject_hash},)))

    return {"nodes": nodes, "edges": edges}


def apply_operation_projection(graph: Graph, projection: dict[str, list]
                               ) -> dict[str, int]:
    """Fold an operation projection into a graph — merges like any
    other layer via evidence records."""
    for n in projection["nodes"]:
        graph.add_node(n)
    for e in projection["edges"]:
        graph.add_edge(e)
    return {"nodes_added": len(projection["nodes"]),
            "edges_added": len(projection["edges"])}


def operation_only(graph: Graph) -> Graph:
    """Query helper — subgraph of the operational layer only.
    Non-operational endpoint nodes (e.g. a mutated workload) are
    carried in so edges stay resolvable."""
    sub = Graph()
    for n in graph.nodes.values():
        if n.kind in ("operation", "change_intent", "change_plan",
                      "execution_envelope", "approval", "runbook",
                      "platform_request", "policy_decision"):
            sub.add_node(n)
    for e in graph.edges.values():
        if e.kind in ("intends", "planned_by", "mutates", "approved_by",
                      "executed_by", "verifies", "rolled_back_by",
                      "requested_by", "produced_receipt"):
            for nid in (e.src, e.dst):
                if nid not in sub.nodes and nid in graph.nodes:
                    sub.add_node(graph.nodes[nid])
            sub.add_edge(e)
    return sub
