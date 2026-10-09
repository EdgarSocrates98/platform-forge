"""Runtime topology (cycle §117–§125) — OTel / Hubble / EndpointSlice →
runtime edges with temporal windows + behavior classes.

Rules that keep this honest:
- §121 — runtime edges are `provenance=observed` + `source_type=runtime`
  (measured evidence); they never overwrite declared edges — the v2
  evidence list keeps both layers.
- §123 — only whitelisted attributes survive extraction: service names,
  namespaces, ports, protocols, verdicts. URLs, headers, db.statement,
  user ids, payloads are dropped at the boundary (§208).
- §92 — a runtime edge with no samples in a window is "not recently
  observed", never "the dependency does not exist".
"""

from __future__ import annotations

from typing import Any

from platformforge.graph.model import node_id
from platformforge.live.models import BEHAVIOR_CLASSES, now_iso

# §123/§208 — extraction whitelist. Anything not listed is dropped.
SAFE_RESOURCE_ATTRS = ("service.name", "service.namespace",
                       "k8s.namespace.name", "k8s.deployment.name",
                       "k8s.pod.name")
SAFE_SPAN_ATTRS = ("peer.service", "server.address", "network.peer.name",
                   "db.system", "db.name", "messaging.system",
                   "messaging.destination.name", "rpc.service",
                   "server.port", "url.template")
DROP_ATTR_MARKERS = ("url", "header", "statement", "query", "user",
                     "password", "token", "secret", "body", "payload",
                     "cookie", "authorization")


def _attrs_of(span_or_resource: dict[str, Any]) -> dict[str, Any]:
    """OTLP attributes[] → plain dict, whitelist-filtered."""
    raw = span_or_resource.get("attributes") or {}
    if isinstance(raw, list):
        raw = {a.get("key"): (a.get("value") or {})
               for a in raw if isinstance(a, dict)}
    out = {}
    for k, v in raw.items():
        lk = str(k).lower()
        if any(m in lk for m in DROP_ATTR_MARKERS) and \
                lk not in SAFE_SPAN_ATTRS:
            continue
        if k in SAFE_RESOURCE_ATTRS or k in SAFE_SPAN_ATTRS:
            out[k] = v.get("stringValue") or v.get("intValue") \
                if isinstance(v, dict) else v
    return out


def _service_node(attrs: dict[str, Any]) -> str:
    name = attrs.get("service.name") or attrs.get("service") or "unknown"
    ns = attrs.get("service.namespace") or \
        attrs.get("k8s.namespace.name") or ""
    return node_id("service", f"{ns}/{name}" if ns else str(name))


def _peer_node(attrs: dict[str, Any]) -> tuple[str, str]:
    """Resolve a span's remote peer to (node_id, edge_kind)."""
    if attrs.get("db.system"):
        return node_id("database", str(attrs.get("db.name")
                                            or attrs["db.system"])), "calls"
    if attrs.get("messaging.system"):
        return node_id("queue", str(
            attrs.get("messaging.destination.name")
            or attrs["messaging.system"])), "consumes"
    peer = attrs.get("peer.service") or attrs.get("server.address") or \
        attrs.get("rpc.service") or attrs.get("network.peer.name")
    if peer:
        return node_id("service", str(peer)), "calls"
    return "", ""


def edges_from_otel(docs: list[dict[str, Any]], *,
                    window_start: str = "", window_end: str = ""
                    ) -> list[dict[str, Any]]:
    """OTLP span docs → runtime edge records {src,dst,kind,temporal,
    evidence,attrs}. Accepts `resourceSpans` trees and pre-flattened
    {service, peer, ...} dicts."""
    pairs: dict[tuple[str, str, str], dict[str, Any]] = {}
    flat: list[dict[str, Any]] = []
    for d in docs:
        if "resourceSpans" in d:
            for rs in d["resourceSpans"]:
                res_attrs = _attrs_of(rs.get("resource", {}))
                svc = _service_node(res_attrs)
                for ss in rs.get("scopeSpans", []):
                    for sp in ss.get("spans", []):
                        flat.append({"service_node": svc,
                                     "attrs": _attrs_of(sp)})
        else:
            flat.append(d)
    for s in flat:
        svc = s.get("service_node") or _service_node(
            s.get("attrs", {}) or s)
        peer, kind = _peer_node(s.get("attrs", {}) or s)
        if not svc or not peer or svc == peer:
            continue
        key = (svc, peer, kind)
        rec = pairs.setdefault(key, {"src": svc, "dst": peer,
                                     "kind": kind, "sample_count": 0,
                                     "first_seen": "", "last_seen": ""})
        rec["sample_count"] += 1
    out = []
    for rec in pairs.values():
        rec["first_seen"] = window_start or now_iso()
        rec["last_seen"] = window_end or now_iso()
        rec["provenance"] = "observed"
        rec["source_type"] = "otel"
        out.append(rec)
    return sorted(out, key=lambda r: (r["src"], r["dst"], r["kind"]))


def _hubble_ep(ep: dict[str, Any]) -> str:
    pod = ep.get("pod_name") or ""
    ns = ep.get("namespace") or ""
    if pod:
        return node_id("pod", f"{ns}/{pod}" if ns else pod)
    for l in ep.get("labels", []) or []:
        if l.startswith(("k8s:app=", "k8s:name=")):
            return node_id("workload", l.split("=", 1)[1])
    return node_id("service", f"ext:{ep.get('ip')}") \
        if ep.get("ip") else ""


def edges_from_hubble(flows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Hubble flow docs → runtime edges; verdicts kept as evidence."""
    pairs: dict[tuple[str, str], dict[str, Any]] = {}
    for f in flows:
        fl = f.get("flow", f)
        src = _hubble_ep(fl.get("source", {}))
        dst = _hubble_ep(fl.get("destination", {}))
        if not src or not dst or src == dst:
            continue
        key = (src, dst)
        rec = pairs.setdefault(key, {"src": src, "dst": dst,
                                     "kind": "calls", "sample_count": 0,
                                     "verdicts": {}, "ports": set(),
                                     "first_seen": "", "last_seen": ""})
        rec["sample_count"] += 1
        v = fl.get("verdict", "")
        if v:
            rec["verdicts"][v] = rec["verdicts"].get(v, 0) + 1
        port = ((fl.get("l4") or {}).get("TCP") or {}).get(
            "destination_port")
        if port:
            rec["ports"].add(port)
        t = f.get("time") or fl.get("time", "")
        if t:
            rec["first_seen"] = min(t, rec["first_seen"] or t)
            rec["last_seen"] = max(t, rec["last_seen"] or t)
    out = []
    for rec in pairs.values():
        rec["provenance"] = "observed"
        rec["source_type"] = "hubble"
        rec["attrs"] = {"ports": sorted(rec.pop("ports")),
                        "verdicts": rec.pop("verdicts")}
        out.append(rec)
    return sorted(out, key=lambda r: (r["src"], r["dst"]))


def edges_from_endpointslices(objects: list[dict[str, Any]]
                              ) -> list[dict[str, Any]]:
    """EndpointSlice k8s objects → workload→service membership edges."""
    out = []
    for o in objects:
        # accept raw k8s EndpointSlice or projected ObservedObject
        eps = o.get("endpoints") or \
            (o.get("attributes", {}).get("endpoints") or [])
        labels = o.get("metadata", {}).get("labels", {}) or \
            o.get("attributes", {}).get("labels", {})
        svc = (labels.get("kubernetes.io/service-name")
               or o.get("service_name") or "")
        ns = o.get("metadata", {}).get("namespace", "") or \
            o.get("namespace", "")
        if not svc:
            continue
        for ep in eps:
            ref = ep.get("targetRef", {})
            if ref.get("kind") != "Pod":
                continue
            pod = node_id("pod", f"{ref.get('namespace') or ns}/"
                                 f"{ref.get('name')}")
            out.append({"src": pod,
                        "dst": node_id("service", f"{ns}/{svc}"),
                        "kind": "exposes", "provenance": "observed",
                        "source_type": "endpointslice",
                        "sample_count": 1})
    return sorted(out, key=lambda r: (r["src"], r["dst"]))


def classify_behavior(runtime_edges: list[dict[str, Any]],
                      declared_edge_ids: set[str],
                      *, window_fresh: bool = True) -> list[dict[str, Any]]:
    """§125 — declared-vs-runtime behavior class per runtime edge."""
    out = []
    for e in runtime_edges:
        eid = f"{e['src']}->{e['dst']}:{e['kind']}"
        declared = eid in declared_edge_ids
        if declared:
            cls = "declared-and-observed"
        else:
            cls = "observed-undeclared"
        if not window_fresh and declared:
            cls = "declared-not-seen-in-window"
        assert cls in BEHAVIOR_CLASSES
        out.append({**e, "edge_id": eid, "behavior": cls})
    return out


def runtime_temporal(e: dict[str, Any]) -> dict[str, Any]:
    """Normalize an edge record into a v2 temporal block."""
    return {k: v for k, v in {
        "first_seen": e.get("first_seen"),
        "last_seen": e.get("last_seen"),
        "window_start": e.get("window_start") or e.get("first_seen"),
        "window_end": e.get("window_end") or e.get("last_seen"),
        "sample_count": e.get("sample_count", 0)}.items()
        if v not in (None, "")}


def apply_runtime_edges(graph, edges: list[dict[str, Any]]) -> int:
    """Fold runtime edge records into a v2 graph: nodes auto-created as
    `external`/`workload` placeholders when missing; the edge carries a
    `source_type` evidence record + temporal window (§121). Returns the
    number of edges applied."""
    from platformforge.graph.model import Edge, Node
    applied = 0
    for e in edges:
        for nid in (e["src"], e["dst"]):
            if nid not in graph.nodes:
                kind = nid.split("/", 1)[0] or "workload"
                graph.add_node(Node(nid, kind, nid.split("/")[-1]))
        applied_e = graph.add_edge(Edge(
            e["src"], e["dst"], e.get("kind", "calls"),
            provenance="observed",
            confidence=float(e.get("confidence", 1.0)),
            source_fact_ids=tuple(e.get("fact_ids", [])),
            attrs=e.get("attrs", {}),
            evidence=({"provenance": "observed",
                       "source_type": e.get("source_type", "runtime"),
                       "fact_ids": list(e.get("fact_ids", [])),
                       "observed_at": e.get("last_seen", "")},),
            temporal=runtime_temporal(e)))
        if applied_e:
            applied += 1
    return applied
