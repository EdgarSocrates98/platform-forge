"""Cycle 5 Phase L — FleetContextPack (§213–219).

Never load the full fleet into model context (§214). Hierarchical
summary layers with per-layer budgets (§217–219): org → fleet →
cluster → resource detail, drill-down on demand (§218). Selection is
signal-driven (§216), deterministic, never an LLM call (§224–226).
"""

from __future__ import annotations

import json
from typing import Any

SELECTION_SIGNALS = ("task_scope", "fleet_scope", "team", "environment",
                     "recent_changes", "risk", "hotspots",
                     "graph_centrality", "incidents", "cost_anomaly")
LAYERS = ("organization", "fleet", "cluster", "resource")

# per-layer token budget defaults — cheapest sufficient first (§219)
DEFAULT_BUDGETS = {"organization": 200, "fleet": 400, "cluster": 800,
                   "resource": 1600}


def _est_tokens(obj: Any) -> int:
    return max(1, len(json.dumps(obj, sort_keys=True,
                                 default=str)) // 4)


def fleet_context_pack(signals: dict[str, Any],
                       org_summary: dict[str, Any] | None = None,
                       fleet_summaries: list[dict[str, Any]] | None = None,
                       cluster_details: list[dict[str, Any]] | None = None,
                       resource_details: list[dict[str, Any]] | None = None,
                       budgets: dict[str, int] | None = None
                       ) -> dict[str, Any]:
    """§215–219 — build the pack bottom-up *within budget*.

    Layers fill cheapest-first; overflow is reported as `deferred`
    (drill-down handles it later — §218), never silently truncated.
    """
    b = {**DEFAULT_BUDGETS, **(budgets or {})}
    pack: dict[str, Any] = {
        "schema": "platformforge/fleet-context-pack/v1",
        "selection_signals": {k: signals[k] for k in SELECTION_SIGNALS
                              if k in signals},
        "layers": {}, "deferred": [], "budgets": b}
    sources = {"organization": org_summary,
               "fleet": fleet_summaries or [],
               "cluster": cluster_details or [],
               "resource": resource_details or []}
    used = 0
    for layer in LAYERS:
        data = sources[layer]
        items = data if isinstance(data, list) else ([data] if data else [])
        kept, deferred = [], 0
        for item in items:
            cost = _est_tokens(item)
            if used + cost <= b[layer]:
                kept.append(item)
                used += cost
            else:
                deferred += 1
        pack["layers"][layer] = {"items": kept, "tokens": sum(
            _est_tokens(i) for i in kept)}
        if deferred:
            pack["deferred"].append({"layer": layer, "count": deferred,
                                     "drill_down": True})
    pack["total_tokens"] = used
    pack["full_fleet_loaded"] = False      # §214 — by construction
    return pack


def drill_down(pack: dict[str, Any], layer: str,
               items: list[dict[str, Any]],
               budget: int = 1600) -> dict[str, Any]:
    """§218 — expand one layer on demand, still budgeted."""
    kept, cost, deferred = [], 0, 0
    for item in items:
        t = _est_tokens(item)
        if cost + t <= budget:
            kept.append(item)
            cost += t
        else:
            deferred += 1
    return {"layer": layer, "items": kept, "tokens": cost,
            "deferred": deferred}
