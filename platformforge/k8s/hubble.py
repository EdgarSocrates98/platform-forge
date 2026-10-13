"""§67 Hubble — Cilium flow dumps → T1 provider-observed network facts.

Configured policies (CiliumNetworkPolicy in manifests) stay T3 — flow
records are *measured traffic* and must not share a fact tier. Each flow
becomes an observed edge between workload/identity nodes; drops and L7
verdicts are surfaced for the policy graph to compare against intent.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from platformforge.models.base import stable_id


def _ep_label(ep: dict[str, Any] | None) -> str:
    if not ep:
        return "unknown"
    pod = ep.get("pod_name") or ""
    if pod:
        return pod
    lbls = ep.get("labels") or []
    for l in lbls:
        if l.startswith(("k8s:app=", "k8s:name=")):
            return l.split("=", 1)[1]
    return ep.get("ip") or "unknown"


def analyze_hubble(path: str | Path) -> dict[str, Any]:
    """Parse hubble observe JSON/JSONL output → observed flow facts."""
    root = Path(path)
    files = sorted(root.rglob("*.json*")) if root.is_dir() else [root]
    flows: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    for f in files:
        text = f.read_text(errors="replace").strip()
        docs: list[Any] = []
        try:
            parsed = json.loads(text)
            docs = parsed if isinstance(parsed, list) else [parsed]
        except json.JSONDecodeError:
            for line in text.splitlines():
                try:
                    docs.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        if not docs:
            unresolved.append({"location": str(f),
                               "reason": "no hubble flow records parsed"})
        for d in docs:
            flow = d.get("flow") or d  # hubble wraps in {"flow": {...}}
            if not isinstance(flow, dict) or "IP" not in flow \
                    and "l4" not in {k.lower() for k in flow}:
                continue
            flows.append({"flow": flow, "file": str(f)})

    # aggregate flows into observed edges — one fact per src→dst pair
    pairs: dict[tuple[str, str], dict[str, Any]] = {}
    for rec in flows:
        fl = rec["flow"]
        src, dst = _ep_label(fl.get("source")), _ep_label(fl.get("destination"))
        key = (src, dst)
        agg = pairs.setdefault(key, {"flows": 0, "dropped": 0, "files": set()})
        agg["flows"] += 1
        if fl.get("verdict") == "DROPPED":
            agg["dropped"] += 1
        agg["files"].add(rec["file"])

    facts: list[dict[str, Any]] = []
    for (src, dst), agg in sorted(pairs.items()):
        facts.append({
            "fact_id": stable_id("PF-HUBBLE", "flow", f"{src}->{dst}"),
            "kind": "cilium.flow", "source": min(agg["files"]),
            "location": f"{src} -> {dst}",
            "tier": 1,  # provider-observed runtime traffic
            "attrs": {"source": src, "destination": dst,
                      "flows": agg["flows"], "dropped": agg["dropped"],
                      "graph": {
                          "nodes": [{"kind": "workload", "label": src},
                                    {"kind": "workload", "label": dst}],
                          "edges": [{"src_kind": "workload", "src": src,
                                     "dst_kind": "workload", "dst": dst,
                                     "kind": "calls"}]}}})
    return {"facts": facts, "unresolved": unresolved,
            "counts": {"flows": len(flows), "pairs": len(facts)}}
