"""Cycle 5 Phase B — fleet questions (§27).

Each question is a deterministic graph query over the federated org
graph; answers carry node ids + fact evidence, and the caller gets the
snapshot coverage alongside — never an org-wide claim from a partial
fleet (§374/§391).
"""

from __future__ import annotations

from typing import Any

from platformforge.fleet.orggraph import layer_of
from platformforge.graph.model import Graph

# question id → human label (§27)
FLEET_QUESTIONS = {
    "public-services": "all services with public exposure",
    "critical-services": "services marked critical (declared evidence)",
    "unsupported-k8s": "workloads on unsupported kubernetes versions",
    "wildcard-iam": "IAM roles/principals with wildcard permissions",
    "unowned": "resources without an owning team",
    "no-slo": "services without an SLO definition",
    "outside-golden-path": "services not using a golden path",
    "idle-high-cost": "high-cost workloads flagged idle/underused",
    "cross-env-deps": "dependencies that cross environment boundaries",
}


def fleet_query(graph: Graph, question: str) -> dict[str, Any]:
    fn = _QUESTIONS.get(question)
    if fn is None:
        raise ValueError(f"unknown fleet question: {question}")
    hits = fn(graph)
    return {"question": question, "count": len(hits), "items": hits}


def _fact_ids(n) -> list[str]:
    return list(n.source_fact_ids)


def _public_services(g: Graph) -> list[dict[str, Any]]:
    out = []
    for n in g.nodes.values():
        if n.kind in ("service", "workload") and (
                n.attrs.get("exposure") == "public"
                or n.attrs.get("public") is True):
            out.append({"node_id": n.node_id, "layer": layer_of(n.kind),
                        "fact_ids": _fact_ids(n)})
    # ingress/load-balancer exposure counts as public too
    for e in g.edges.values():
        if e.kind == "exposes" and e.src in g.nodes:
            src = g.nodes[e.src]
            if src.kind in ("service", "workload") and all(
                    h["node_id"] != src.node_id for h in out):
                out.append({"node_id": src.node_id,
                            "layer": layer_of(src.kind),
                            "fact_ids": list(e.source_fact_ids)})
    return out


def _critical_services(g: Graph) -> list[dict[str, Any]]:
    return [{"node_id": n.node_id, "criticality": n.attrs["criticality"],
             "fact_ids": _fact_ids(n)}
            for n in g.nodes.values()
            if n.kind in ("service", "workload")
            and n.attrs.get("criticality") in ("critical", "high")]


def _unsupported_k8s(g: Graph) -> list[dict[str, Any]]:
    return [{"node_id": n.node_id, "version": n.attrs.get("k8s_version"),
             "fact_ids": _fact_ids(n)}
            for n in g.nodes.values()
            if n.attrs.get("supported") is False
            or n.attrs.get("k8s_support") == "unsupported"]


def _wildcard_iam(g: Graph) -> list[dict[str, Any]]:
    return [{"node_id": n.node_id, "fact_ids": _fact_ids(n)}
            for n in g.nodes.values()
            if n.kind in ("iam_principal", "role", "policy")
            and n.attrs.get("wildcard") is True]


def _unowned(g: Graph) -> list[dict[str, Any]]:
    owned = {e.dst for e in g.edges.values() if e.kind == "owns"}
    owned |= {e.src for e in g.edges.values() if e.kind == "owns"}
    return [{"node_id": n.node_id, "layer": layer_of(n.kind)}
            for n in g.nodes.values()
            if n.kind in ("service", "workload", "repository",
                          "database", "cluster")
            and n.node_id not in owned]


def _no_slo(g: Graph) -> list[dict[str, Any]]:
    slo_targets = {e.src for e in g.edges.values()
                   if g.nodes.get(e.dst) and
                   g.nodes[e.dst].kind == "slo"}
    has_slo_attr = {n.node_id for n in g.nodes.values()
                    if n.attrs.get("slo")}
    return [{"node_id": n.node_id, "fact_ids": _fact_ids(n)}
            for n in g.nodes.values()
            if n.kind in ("service", "workload")
            and n.node_id not in slo_targets | has_slo_attr]


def _outside_golden_path(g: Graph) -> list[dict[str, Any]]:
    on_path = {e.src for e in g.edges.values()
               if e.kind == "uses_golden_path"}
    services = {n.node_id for n in g.nodes.values()
                if n.kind in ("service", "workload")}
    return [{"node_id": nid} for nid in sorted(services - on_path)]


def _idle_high_cost(g: Graph) -> list[dict[str, Any]]:
    out = []
    for n in g.nodes.values():
        idle = n.attrs.get("idle") or n.attrs.get("underused")
        cost = n.attrs.get("cost_monthly") or n.attrs.get("cost_usd")
        if idle and isinstance(cost, (int, float)) and cost > 0:
            out.append({"node_id": n.node_id, "cost_monthly": cost,
                        "idle_signal": n.attrs.get("idle_signal", "obs"),
                        "fact_ids": _fact_ids(n)})
    return sorted(out, key=lambda h: -h["cost_monthly"])


def _cross_env_deps(g: Graph) -> list[dict[str, Any]]:
    out = []
    for e in g.edges.values():
        if e.kind not in ("depends_on", "calls", "reads", "writes",
                          "consumes"):
            continue
        a, b = g.nodes.get(e.src), g.nodes.get(e.dst)
        if not a or not b:
            continue
        ea, eb = a.attrs.get("environment"), b.attrs.get("environment")
        if ea and eb and ea != eb:
            out.append({"from": e.src, "to": e.dst, "kind": e.kind,
                        "envs": [ea, eb],
                        "fact_ids": list(e.source_fact_ids)})
    return out


_QUESTIONS = {
    "public-services": _public_services,
    "critical-services": _critical_services,
    "unsupported-k8s": _unsupported_k8s,
    "wildcard-iam": _wildcard_iam,
    "unowned": _unowned,
    "no-slo": _no_slo,
    "outside-golden-path": _outside_golden_path,
    "idle-high-cost": _idle_high_cost,
    "cross-env-deps": _cross_env_deps,
}
