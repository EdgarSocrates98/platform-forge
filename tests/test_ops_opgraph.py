"""Phase R/S gates — operational graph projection + capability v3 +
cross-forge delegation."""

from platformforge.forge.manifest import capability_manifest
from platformforge.graph.model import Graph
from platformforge.ops.envelope import ExecutionEnvelope
from platformforge.ops.operation import Operation, OperationLedger
from platformforge.ops.opgraph import apply_operation_projection, operation_only, project_operation
from platformforge.ops.registry import delegation_contract, ops_capabilities, validate_delegate_request


def _env():
    e = ExecutionEnvelope(
        execution_id="ex1", intent_id="i1",
        change_plan_hash="sha256:x", executor="kubernetes",
        actions=[{"step_id": "s1", "action": "kubernetes.scale",
                  "params": {"kind": "Deployment", "name": "web",
                             "replicas": 3}}],
        scope=["k8s:prod/apps/Deployment/web"])
    e.freeze()
    return e


def test_projection_nodes_edges_cite_receipts():
    env = _env()
    op = Operation(operation_id="op1", intent_id="i1",
                   resources=list(env.scope))
    led = OperationLedger()
    led.append("created", "op1")
    led.append("approved", "op1")
    proj = project_operation(op, envelope=env, ledger=led)
    kinds = {n.kind for n in proj["nodes"]}
    assert {"operation", "change_intent", "execution_envelope",
            "workload"} <= kinds
    ekinds = {e.kind for e in proj["edges"]}
    assert {"intends", "executed_by", "mutates"} <= ekinds
    for e in proj["edges"]:
        assert e.layers()[0].get("layer") == "operation"
        assert e.layers()[0].get("receipt_ids") is not None \
            or "envelope_hash" in e.layers()[0]


def test_operational_layer_is_separable():
    g = Graph()
    # platform dependency edge
    from platformforge.graph.model import Edge, Node
    g.add_node(Node.make("service", "web"))
    g.add_node(Node.make("database", "pg"))
    g.add_edge(Edge("service/web", "database/pg", "depends_on"))
    proj = project_operation(
        Operation(operation_id="op1", intent_id="i1"),
        envelope=_env(), ledger=OperationLedger())
    apply_operation_projection(g, proj)
    sub = operation_only(g)
    assert "depends_on" not in {e.kind for e in sub.edges.values()}
    assert "service/web" not in sub.nodes


def test_manifest_v3_exposes_ops():
    m = capability_manifest()
    assert m["manifest"] == "platformforge/capability-manifest/v3"
    assert m["modes"]["governed_mutation"] is True
    assert m["operations"]["platform_max_autonomy"] == "A4"
    assert m["operations"]["a6"] == "non-goal"
    assert "kubernetes.scale" in m["operations"]["actions"]
    assert m["cross_forge"]["refusal_code"] == "PF-OPS-CROSSFORGE-REFUSED"


def test_delegation_never_executes():
    assert delegation_contract()["refuses"]
    for bad in ("direct-execution", "approval-minting",
                "shell-command", "generic-provider-call"):
        assert bad in delegation_contract()["refuses"] or \
            bad in delegation_contract()["refuses"]
    r = validate_delegate_request({"kind": "change-intent",
                                   "requested_by": "forge-x"})
    assert r["ok"] and r["route"] == "change-intent"
    r2 = validate_delegate_request({"kind": "direct-execution"})
    assert r2["refusal"] == "PF-OPS-CROSSFORGE-REFUSED"
    r3 = validate_delegate_request({"kind": "change-intent"})
    assert r3["refusal"] == "PF-OPS-NO-ACTOR"


def test_ops_caps_declare_autonomy():
    caps = ops_capabilities()
    assert caps["executors"]["kubernetes"]["max_autonomy"] == \
        "A5-lab-only"
    assert caps["executors"]["observe"]["mutates"] is False


# --- Cycle 4.1 §I — graph completeness validation ---------------------

def test_projection_complete_no_orphans():
    from platformforge.ops.opgraph import validate_projection
    env = _env()
    op = Operation(operation_id="op1", intent_id="i1",
                   resources=list(env.scope))
    led = OperationLedger()
    led.append("created", "op1")
    led.append("step.completed", "op1",
               data={"step_id": "s1", "receipt": "rcpt-1"})
    mats = {"s1": {"hash": "mat-abc", "pre_state": {"replicas": 3}}}
    proj = project_operation(op, envelope=env, ledger=led,
                             materials=mats)
    assert validate_projection(proj) == []
    mut = next(e for e in proj["edges"] if e.kind == "mutates")
    assert mut.layers()[0]["material_hash"] == "mat-abc"
    assert mut.layers()[0]["step_receipt"] == "rcpt-1"


def test_rollback_edge_cites_receipt_and_material():
    env = _env()
    op = Operation(operation_id="op1", intent_id="i1")
    led = OperationLedger()
    led.append("rollback.completed", "op1",
               data={"strategy": "direct-inverse",
                     "rollback_verification": "restored"})
    proj = project_operation(op, envelope=env, ledger=led,
                             rollback_receipt={
                                 "strategy": "direct-inverse",
                                 "trigger": {"type": "verification-fail"},
                                 "material_hashes": ["m1"],
                                 "result": "restored"})
    rb = [e for e in proj["edges"] if e.kind == "rolled_back_by"]
    assert rb and rb[0].layers()[0]["material_hashes"] == ["m1"]
    assert rb[0].layers()[0]["receipt_ids"]


def test_validate_projection_flags_orphan_and_missing_receipt():
    from platformforge.graph.model import Edge, Node
    from platformforge.ops.opgraph import validate_projection
    orphan = Node.make("operation", "lonely")
    proj = {"nodes": [orphan], "edges": []}
    assert "orphan-node:operation:lonely" in validate_projection(proj)
    a = Node.make("operation", "o"); b = Node.make("approval", "ap")
    edge = Edge(a.node_id, b.node_id, "approved_by",
                provenance="observed",
                evidence=({"provenance": "observed",
                           "layer": "operation"},))
    gaps = validate_projection({"nodes": [a, b], "edges": [edge]})
    assert any("approved_by" in g for g in gaps)


# --- §128–129 — golden path uses the governed contracts ---------------

def test_platform_request_bridges_to_change_intent():
    from platformforge.ops.goldenpath import PlatformRequest
    r = PlatformRequest(request_id="r1", requester="edgar",
                        team="platform", kind="service",
                        template="web-svc", environment="staging",
                        params={"resources": ["k8s:x/y/Deployment/z"]})
    intent = r.to_change_intent()
    d = intent.to_dict()
    assert d["intent_id"] == "req-r1"
    assert "k8s:x/y/Deployment/z" in intent.target_resources
    assert intent.desired_change["template"] == "web-svc"
