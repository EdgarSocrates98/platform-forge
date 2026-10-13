"""§85 Prometheus — offline ingestion of rule files and query exports.

Rules (PrometheusRule CRDs or prometheus.yml `groups[].rules[]`) are T3
declared config. Query exports (instant/range JSON `data.result[]`) are
T1 provider-observed measurements. The two never share a tier.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from platformforge.models.base import stable_id


def _rule_groups(doc: dict[str, Any]) -> list[dict[str, Any]]:
    spec = doc.get("spec") or doc
    return [g for g in spec.get("groups") or [] if isinstance(g, dict)]


def analyze_prometheus(path: str | Path) -> dict[str, Any]:
    root = Path(path)
    files = (sorted(root.rglob("*.yaml")) + sorted(root.rglob("*.yml")) +
             sorted(root.rglob("*.json"))) if root.is_dir() else [root]
    facts: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []

    for f in files:
        try:
            text = f.read_text()
            doc = (yaml.safe_load(text) if f.suffix in (".yaml", ".yml")
                   else json.loads(text))
        except (OSError, yaml.YAMLError, json.JSONDecodeError):
            continue
        if not isinstance(doc, dict):
            continue
        # Prometheus query export: {"status":"success","data":{"result":[...]}}
        if isinstance(doc.get("data"), dict) and \
                isinstance(doc["data"].get("result"), list):
            for series in doc["data"]["result"]:
                metric = series.get("metric") or {}
                name = metric.get("__name__", "?")
                val = series.get("value") or series.get("values")
                facts.append({
                    "fact_id": stable_id("PF-PROM", "series",
                                         f"{f}:{name}:{len(facts)}"),
                    "kind": "prometheus.series", "source": str(f),
                    "location": name, "tier": 1,  # measured
                    "attrs": {"metric": name, "labels": metric,
                              "points": len(val) if isinstance(val, list)
                              else (1 if val else 0),
                              "result_type": doc["data"].get("resultType")}})
            continue
        # Rule files: groups[].rules[] (native or PrometheusRule CRD)
        groups = _rule_groups(doc)
        for g in groups:
            for r in g.get("rules") or []:
                if not isinstance(r, dict):
                    continue
                is_alert = "alert" in r
                name = r.get("alert") or r.get("record") or "?"
                loc = f"{f}::{g.get('name', '?')}/{name}"
                expr = str(r.get("expr", ""))
                facts.append({
                    "fact_id": stable_id("PF-PROM", "rule", loc),
                    "kind": "prometheus.alert" if is_alert
                            else "prometheus.recording",
                    "source": str(f), "location": loc, "tier": 3,
                    "attrs": {
                        "name": name, "group": g.get("name"),
                        "kind": "alert" if is_alert else "record",
                        "expr": expr, "for": r.get("for"),
                        "severity": (r.get("labels") or {}).get("severity"),
                        "has_runbook": bool(
                            (r.get("annotations") or {}).get("runbook_url")),
                        "service_refs": sorted({
                            p.split('"')[0]
                            for p in expr.split('service="')[1:]})
                            if 'service="' in expr else [],
                        "graph": {
                            "nodes": [{"kind": "alert", "label": name}]
                            if is_alert else [],
                            "edges": []}}})
    return {"facts": facts, "unresolved": unresolved,
            "counts": {"facts": len(facts)}}
