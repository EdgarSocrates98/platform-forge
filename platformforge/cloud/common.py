"""Cloud common model (§49) — provider-neutral resource facts.

Facts here are *provider-observed* (EvidenceTier 1) when they come from
CLI/API dumps, never mixed with declared config. Each fact contributes
graph nodes/edges in the provider-neutral vocabulary.
"""

from __future__ import annotations

from typing import Any

from platformforge.core.redaction import redact_obj
from platformforge.models.base import EvidenceTier, stable_id

# §49 — provider-neutral resource type → (node kind, default edge target)
RESOURCE_KIND_MAP = {
    "organization": "organization", "account": "cloud_account",
    "subscription": "cloud_account", "project": "cloud_account",
    "region": "region", "zone": "zone",
    "role": "role", "policy": "policy", "principal": "iam_principal",
    "workload_identity": "workload_identity",
    "vpc": "vpc_vnet", "subnet": "subnet", "route_table": "route",
    "internet_gateway": "gateway", "nat_gateway": "nat",
    "transit_gateway": "gateway", "endpoint": "route",
    "load_balancer": "load_balancer", "dns_zone": "dns",
    "instance": "node", "function": "workload", "cluster": "cluster",
    "bucket": "bucket", "database": "database", "cache": "cache",
    "queue": "queue", "topic": "topic", "secret": "secret",
    "certificate": "certificate", "budget": "budget",
    "cost_center": "cost_center",
}


def resource_fact(provider: str, rtype: str, rid: str, *,
                  account: str = "", region: str = "",
                  attrs: dict[str, Any] | None = None,
                  edges: list[dict[str, Any]] | None = None,
                  nodes: list[dict[str, Any]] | None = None,
                  tier: int = EvidenceTier.PROVIDER_OBSERVED,
                  source: str = "") -> dict[str, Any]:
    """One provider-neutral fact carrying graph contributions."""
    kind = RESOURCE_KIND_MAP.get(rtype, "component")
    node_attrs = {"provider": provider, "resource_type": rtype,
                  "account": account, "region": region}
    node_attrs.update(attrs or {})
    graph = {"nodes": [{"kind": kind, "label": rid, "attrs": node_attrs}],
             "edges": []}
    if account:
        graph["nodes"].append({"kind": "cloud_account", "label": account})
        graph["edges"].append({"src_kind": kind, "src": rid,
                               "dst_kind": "cloud_account", "dst": account,
                               "kind": "contained_by"})
    if region:
        graph["nodes"].append({"kind": "region", "label": region})
        graph["edges"].append({"src_kind": kind, "src": rid,
                               "dst_kind": "region", "dst": region,
                               "kind": "contained_by"})
    graph["nodes"].extend(nodes or [])
    graph["edges"].extend(edges or [])
    return {
        "fact_id": stable_id("PF-CLD", f"{provider}.{rtype}", rid),
        "kind": f"cloud.{provider}.{rtype}",
        "source": source or f"{provider}-dump",
        "location": f"{provider}:{account}:{region}:{rid}",
        "tier": int(tier),
        "attrs": {"provider": provider, "resource_type": rtype,
                  "id": rid, "account": account, "region": region,
                  "graph": graph, **redact_obj(attrs or {})},
    }
