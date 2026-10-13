"""Derive §130 risk signals from facts + graph — declared inputs only.

Every signal names its evidence. When evidence is absent the signal is
left unresolved rather than assumed safe."""

from __future__ import annotations

from typing import Any

from platformforge.risk.engine import criticality

_DATA_KINDS = {"database", "bucket", "volume", "cache", "queue"}
_AVAIL_KINDS = {"workload", "slo", "load_balancer", "ingress"}
_ID_KINDS = {"iam_principal", "role", "policy", "workload_identity",
             "service_account"}
_NET_KINDS = {"load_balancer", "ingress", "dns", "gateway", "route"}


def signals_from_graph(graph: Any, node_ids: list[str],
                       blast: dict[str, Any] | None = None) -> dict[str, Any]:
    """Map a blast-radius result + node attrs onto §130 signals."""
    nodes = set(node_ids)
    if blast:
        for cls_nodes in blast.get("by_class", {}).values():
            nodes.update(cls_nodes)
    impacted = [graph.nodes[n] for n in nodes if n in graph.nodes] \
        if hasattr(graph, "nodes") else []
    crit = [criticality(n.attrs) for n in impacted]
    kinds = {n.kind for n in impacted}
    total = blast.get("impacted_total", 0) if blast else 0
    sig: dict[str, Any] = {
        "blast_radius": min(3, total // 3),
        "criticality": ({"critical": 3, "high": 3, "medium": 2, "low": 1}
                        .get(next((c for c in crit if c != "unresolved"),
                                  "unresolved"))
                        if impacted else None),
        "security_impact": (bool(kinds & {"security_policy",
                                         "admission_policy"})
                            if impacted else None),
        "identity_impact": bool(kinds & _ID_KINDS) if impacted else None,
        "network_exposure": bool(kinds & _NET_KINDS) if impacted else None,
        "data_persistence": bool(kinds & _DATA_KINDS) if impacted else None,
        "availability_impact": bool(kinds & _AVAIL_KINDS)
                           if impacted else None,
    }
    prod = [n for n in impacted
            if str(n.attrs.get("env", "")).lower() in ("prod", "production")]
    sig["production"] = bool(prod) if impacted else None
    return sig
