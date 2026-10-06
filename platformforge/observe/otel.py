"""OTel span correlation — JSONL span dumps → per-trace service view.

Input: JSONL of {trace_id, span_id, parent_span_id, service, name,
start_unix_ms, duration_ms, status}. Output is purely structural: services
per trace, error propagation, critical path. No sampling assumptions.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def correlate_spans(path: str | Path) -> dict[str, Any]:
    spans: list[dict[str, Any]] = []
    skipped = 0
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            s = json.loads(line)
            if "trace_id" in s and "span_id" in s:
                spans.append(s)
            else:
                skipped += 1
        except json.JSONDecodeError:
            skipped += 1
    traces: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for s in spans:
        traces[s["trace_id"]].append(s)
    out_traces = []
    svc_errors: dict[str, int] = defaultdict(int)
    svc_calls: dict[str, int] = defaultdict(int)
    for tid, spans_ in traces.items():
        by_id = {s["span_id"]: s for s in spans_}
        services = sorted({s.get("service", "?") for s in spans_})
        errors = [s for s in spans_
                  if str(s.get("status", "")).lower() in ("error", "2")]
        for s in errors:
            svc_errors[s.get("service", "?")] += 1
        for s in spans_:
            svc_calls[s.get("service", "?")] += 1
        # critical path = chain with max summed duration (tree walk)
        children: dict[str | None, list[str]] = defaultdict(list)
        for s in spans_:
            children[s.get("parent_span_id")].append(s["span_id"])
        best: dict[str, Any] = {"dur": 0.0, "path": []}

        def walk(sid: str, dur: float, path: list[str]):
            node = by_id[sid]
            dur += float(node.get("duration_ms") or 0)
            path = path + [f"{node.get('service', '?')}:{node.get('name', '?')}"]
            if dur > best["dur"]:
                best["dur"], best["path"] = dur, path
            for c in children.get(sid, []):
                walk(c, dur, path)

        roots = [s["span_id"] for s in spans_
                 if s.get("parent_span_id") not in by_id]
        for r in roots:
            walk(r, 0.0, [])
        out_traces.append({
            "trace_id": tid, "spans": len(spans_), "services": services,
            "error_spans": len(errors),
            "error_services": sorted({s.get("service", "?")
                                      for s in errors}),
            "critical_path_ms": best["dur"],
            "critical_path": best["path"],
        })
    return {
        "traces": sorted(out_traces, key=lambda t: t["trace_id"]),
        "counts": {"spans": len(spans), "traces": len(traces),
                   "skipped_lines": skipped},
        "service_summary": {
            svc: {"spans": svc_calls[svc], "error_spans": svc_errors.get(svc, 0)}
            for svc in sorted(svc_calls)},
    }
