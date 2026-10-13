"""§86 Grafana — dashboard JSON → facts + `dashboard observes service`.

Dashboards are declared config (T3). Service refs come from panel
expressions (`service="x"` / `service_name="x"` label matchers) and
templated variables — never inferred from titles.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from platformforge.models.base import stable_id

_SVC_RE = re.compile(r'\b(?:service|service_name|service\.name)\s*=\s*"([^"]+)"')


def _walk_panels(doc: dict[str, Any]) -> list[dict[str, Any]]:
    panels: list[dict[str, Any]] = []
    stack = list(doc.get("panels") or [])
    while stack:
        p = stack.pop()
        if not isinstance(p, dict):
            continue
        if p.get("type") == "row":
            stack += p.get("panels") or []
            continue
        panels.append(p)
        stack += p.get("panels") or []
    return panels


def analyze_grafana(path: str | Path) -> dict[str, Any]:
    root = Path(path)
    files = sorted(root.rglob("*.json")) if root.is_dir() else [root]
    facts: list[dict[str, Any]] = []
    for f in files:
        try:
            doc = json.loads(f.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(doc, dict) or "panels" not in doc \
                and "dashboard" not in doc:
            continue
        dash = doc.get("dashboard", doc)
        title = dash.get("title", f.stem)
        panels = _walk_panels(dash)
        datasources = sorted({(p.get("datasource") or {}).get("uid") or
                              (p.get("datasource") or {}).get("type") or "?"
                              for p in panels})
        services: set[str] = set()
        alerts = 0
        for p in panels:
            for t in p.get("targets") or []:
                expr = str(t.get("expr") or t.get("rawSql") or "")
                services |= set(_SVC_RE.findall(expr))
            if p.get("alert") or p.get("type") == "alert":
                alerts += 1
        loc = f"{f}::{title}"
        facts.append({
            "fact_id": stable_id("PF-GRAFANA", "dashboard", loc),
            "kind": "grafana.dashboard", "source": str(f),
            "location": loc, "tier": 3,
            "attrs": {"title": title, "uid": dash.get("uid"),
                      "panels": len(panels), "alerts": alerts,
                      "datasources": datasources,
                      "services": sorted(services),
                      "graph": {
                          "nodes": [{"kind": "dashboard", "label": title}],
                          "edges": [{"src_kind": "service", "src": s,
                                     "dst_kind": "dashboard", "dst": title,
                                     "kind": "observed_by"}
                                    for s in sorted(services)]}}})
    return {"facts": facts, "counts": {"facts": len(facts)}}
