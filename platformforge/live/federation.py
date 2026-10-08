"""Multi-cluster federation (cycle §126–§131).

- ClusterRegistry: declared fleet inventory under
  `.platformforge/clusters/registry.json` — cluster_id, provider,
  account, region, context, environment. Registry entries are declared
  intent; coverage is earned by observations.
- federate(): merges per-cluster graphs into one federated graph.
  Same node_id → merged (evidence unions); cluster origin is stamped
  on every node/edge attr so provenance survives the merge.
- coverage report: which registered clusters actually contributed —
  a registered cluster with no observation is a declared gap, not an
  implicit failure.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from platformforge.graph.model import Edge, Graph, Node
from platformforge.live.models import now_iso

REGISTRY = ".platformforge/clusters/registry.json"


@dataclass
class Cluster:
    cluster_id: str
    provider: str = ""                  # eks|gke|kind|…
    account: str = ""
    region: str = ""
    context: str = ""                   # kube context
    environment: str = ""
    labels: dict[str, str] = field(default_factory=dict)
    registered_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v not in ("", {})}


class ClusterRegistry:
    def __init__(self, root: str | Path):
        self.path = Path(root) / REGISTRY

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"clusters": {}}
        return json.loads(self.path.read_text())

    def _save(self, doc: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(doc, indent=2, sort_keys=True)
                             + "\n")

    def register(self, cluster: Cluster) -> dict[str, Any]:
        doc = self._load()
        c = cluster.to_dict()
        c.setdefault("registered_at", now_iso())
        doc["clusters"][cluster.cluster_id] = c
        self._save(doc)
        return c

    def get(self, cluster_id: str) -> dict[str, Any] | None:
        return self._load()["clusters"].get(cluster_id)

    def list(self) -> list[dict[str, Any]]:
        return [self._load()["clusters"][k]
                for k in sorted(self._load()["clusters"])]

    def unregister(self, cluster_id: str) -> bool:
        doc = self._load()
        if doc["clusters"].pop(cluster_id, None) is not None:
            self._save(doc)
            return True
        return False


def federate(graphs: dict[str, Graph]) -> Graph:
    """Merge {cluster_id: Graph} → federated graph. Deterministic:
    sorted iteration, evidence unions, cluster stamped on attrs."""
    out = Graph()
    for cluster_id in sorted(graphs):
        g = graphs[cluster_id]
        for nid in sorted(g.nodes):
            n = g.nodes[nid]
            attrs = dict(n.attrs)
            attrs["cluster"] = attrs.get("cluster") or cluster_id
            out.add_node(Node(nid, n.kind, n.label, attrs,
                              n.source_fact_ids))
        for eid in sorted(g.edges):
            e = g.edges[eid]
            attrs = dict(e.attrs)
            attrs["cluster"] = attrs.get("cluster") or cluster_id
            out.add_edge(Edge(e.src, e.dst, e.kind, e.provenance,
                              e.confidence, e.source_fact_ids, attrs,
                              e.evidence, dict(e.temporal)))
    return out


def federation_coverage(registry: ClusterRegistry,
                        contributing: list[str]) -> dict[str, Any]:
    """Registered vs contributing clusters — explicit partial coverage."""
    reg = {c["cluster_id"] for c in registry.list()}
    seen = set(contributing)
    missing = sorted(reg - seen)
    unknown = sorted(seen - reg)
    status = ("complete" if not missing else
              "partial" if seen else "unknown")
    return {"status": status, "registered": sorted(reg),
            "contributing": sorted(seen), "missing": missing,
            "unregistered": unknown}
