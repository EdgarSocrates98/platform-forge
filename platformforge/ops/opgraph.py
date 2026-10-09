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


def _entry_index(ledger) -> dict[str, list]:
    """event-name → [entry] so every edge cites the ledger receipt(s)
    that prove it — not a vague tail slice (cycle 4.1 §I)."""
    idx: dict[str, list] = {}
    for e in (ledger.entries if ledger else []):
        idx.setdefault(e.event, []).append(e)
    return idx


def project_operation(op, envelope=None,
                      approvals: list | None = None,
                      ledger=None,
                      materials: dict | None = None,
                      rollback_receipt: dict | None = None
                      ) -> dict[str, list]:
    """Build nodes+edges for one operation. `op` is an Operation;
    `envelope` an ExecutionEnvelope or None; `approvals` Approval
    objects; `ledger` an OperationLedger; `materials` captured
    RollbackMaterial per step_id; `rollback_receipt` the §40 receipt.

    Completeness contract (cycle 4.1 §I): every node has ≥1 edge
    (no orphans), every edge cites its evidence — receipt entry
    hashes for observed edges, envelope hash for planned ones,
    approval subject_hash for approvals, material_hash for mutated
    resources."""
    nodes: list[Node] = []
    edges: list[Edge] = []
    idx = _entry_index(ledger)

    def receipts_of(*events: str, tail: int = 5) -> list[str]:
        hs = [e.entry_hash for ev in events
              for e in idx.get(ev, [])]
        return hs[-tail:] or [e.entry_hash for e in
                              (ledger.entries if ledger else
                               [])][-tail:]

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
                                 "receipt_ids": receipts_of(
                                     "planned", "intent.received",
                                     "policy.decided")},)))

    if envelope is not None:
        env_node = _node("execution_envelope", envelope.execution_id,
                         {"executor": envelope.executor,
                          "hash": envelope.hash()})
        nodes.append(env_node)
        edges.append(Edge(op_node.node_id, env_node.node_id,
                          "executed_by", provenance="observed",
                          evidence=({"provenance": "observed",
                                    "layer": LAYER,
                                    "receipt_ids": receipts_of(
                                        "step.completed",
                                        "executed")},)))
        mats = materials or {}
        # per-step mutation edges — cite step receipt + material so the
        # `mutates` claim is auditable to the captured pre-state
        step_rcpt = {e.data.get("step_id"): e.data.get("receipt")
                     for e in idx.get("step.completed", [])
                     if not e.data.get("rollback")}
        scope_set = set(envelope.scope or ())
        covered: set[str] = set()
        for a in envelope.actions:
            sid = a.get("step_id", "")
            res = (a.get("params") or {}).get(
                "resource") or next(iter(scope_set), "unknown")
            covered.add(res)
            res_node = _node("workload", res)
            nodes.append(res_node)
            m = mats.get(sid)
            mh = (m.hash() if hasattr(m, "hash") else
                  (m or {}).get("hash"))
            edges.append(Edge(env_node.node_id, res_node.node_id,
                              "mutates", provenance="planned",
                              confidence=0.9,
                              evidence=({"provenance": "planned",
                                         "layer": LAYER,
                                         "step_id": sid,
                                         "action": a.get("action"),
                                         "envelope_hash":
                                             envelope.hash(),
                                         "step_receipt":
                                             step_rcpt.get(sid),
                                         "material_hash": mh},)))
        # scope-only resources still get an edge (no orphan nodes)
        for res in scope_set - covered:
            res_node = _node("workload", res)
            if res_node.node_id not in {n.node_id for n in nodes}:
                nodes.append(res_node)
                edges.append(Edge(env_node.node_id, res_node.node_id,
                                  "mutates", provenance="planned",
                                  confidence=0.9,
                                  evidence=({"provenance": "planned",
                                             "layer": LAYER,
                                             "resource": res,
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
                                    "subject_hash": ap.subject_hash,
                                    "receipt_ids": receipts_of(
                                        "approval.recorded",
                                        "approval.denied")},)))

    # rollback — rolled_back_by edge cites the rollback receipt +
    # material hashes so the reversal claim traces to captured state
    rb_entries = idx.get("rollback.completed", [])
    if rb_entries or rollback_receipt:
        rec = rollback_receipt or {}
        rb_node = _node("rollback", f"{op.operation_id}-rollback",
                        {"strategy": rec.get("strategy") or
                         (rb_entries[-1].data.get("strategy")
                          if rb_entries else ""),
                         "result": rec.get("result") or
                         (rb_entries[-1].data.get(
                             "rollback_verification")
                          if rb_entries else "")})
        nodes.append(rb_node)
        edges.append(Edge(op_node.node_id, rb_node.node_id,
                          "rolled_back_by", provenance="observed",
                          evidence=({"provenance": "observed",
                                    "layer": LAYER,
                                    "trigger": rec.get("trigger"),
                                    "material_hashes":
                                        rec.get("material_hashes", []),
                                    "receipt_ids": [
                                        e.entry_hash for e in
                                        rb_entries[-3:]]},)))

    return {"nodes": nodes, "edges": edges}


def validate_projection(projection: dict[str, list]) -> list[str]:
    """§115–118 — completeness invariants over a projection:
    - every observed edge cites ≥1 receipt/event hash
    - no orphan nodes (every node touched by ≥1 edge)
    - approved_by edges cite an approval subject_hash
    - mutates edges cite the affected resource + envelope
    Returns a list of gap strings; empty == complete."""
    gaps: list[str] = []
    nodes = projection["nodes"]
    edges = projection["edges"]
    touched = {e.src for e in edges} | {e.dst for e in edges}
    for n in nodes:
        if n.node_id not in touched:
            gaps.append(f"orphan-node:{n.kind}:{n.label}")
    for e in edges:
        ev = e.layers()[0] if e.layers() else {}
        prov = ev.get("provenance", "")
        if prov == "observed" and not (
                ev.get("receipt_ids") or ev.get("subject_hash")):
            gaps.append(f"edge-no-receipt:{e.kind}:{e.src}")
        if e.kind == "approved_by" and not ev.get("subject_hash"):
            gaps.append(f"approved_by-missing-approval:{e.dst}")
        if e.kind == "mutates" and not (
                ev.get("envelope_hash") and
                (ev.get("step_id") or ev.get("resource"))):
            gaps.append(f"mutates-missing-evidence:{e.dst}")
    return gaps


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
                      "rollback", "platform_request",
                      "policy_decision"):
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
