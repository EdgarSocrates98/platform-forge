"""Incident correlation — alerts × changes × graph proximity → ranked
hypotheses. Emits hypotheses WITH evidence ids; never asserts causality."""

from __future__ import annotations

from typing import Any

from platformforge.graph.model import Graph
from platformforge.graph.query import blast_radius


def correlate(alerts: list[dict[str, Any]],
              changes: list[dict[str, Any]],
              graph: Graph | None = None,
              window_s: int = 3600) -> dict[str, Any]:
    """For each alert, rank candidate changes by (a) temporal proximity to
    first alert and (b) graph proximity to the alerted node."""
    hyps: list[dict[str, Any]] = []
    for al in alerts:
        svc = al.get("service") or al.get("node") or al.get("target")
        at = float(al.get("at") or 0)
        cands = []
        for ch in changes:
            tgt = ch.get("target") or ch.get("service")
            dt = at - float(ch.get("at") or 0)
            if dt < -window_s or dt > window_s:
                continue  # change far from alert — out of window
            proximity = "unknown"
            if graph is not None and svc and tgt:
                br = blast_radius(graph, tgt)
                if svc == tgt:
                    proximity = "self"
                elif svc in br["nodes"]:
                    proximity = f"graph-depth-{br['nodes'][svc]['depth']}"
            score = (2 if proximity == "self" else
                     1 if proximity.startswith("graph-depth") else 0) \
                + (1 if 0 <= dt <= window_s else 0)  # change before alert
            cands.append({"change": ch, "dt_seconds": dt,
                          "proximity": proximity, "score": score})
        cands.sort(key=lambda c: (-c["score"], abs(c["dt_seconds"])))
        hyps.append({"alert": al, "hypotheses": cands,
                     "note": "correlation is not causation — hypothesis "
                             "list, not diagnosis"})
    return {"incident_hypotheses": hyps,
            "counts": {"alerts": len(alerts), "changes": len(changes)}}
