"""Cycle 5 §316 — fleet / analytics / optimize / ai / federation
CLI namespaces. All bounded and read-only: they consume a *fleet
directory* (see `fleet.loader.FLEET_FILES` — same shape as lab
fixtures) and emit evidence-cited JSON. Nothing here mutates; the
only action bridge is `optimize plan`, which emits a governed
ChangeIntent doc — it does not execute.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from platformforge.fleet.loader import fleet_from, graph_from_doc, load_fleet_dir
from platformforge.fleet.models import FleetSnapshot, MemberObservation

_NO_DIR = {"refusal": "PF-FLEET-NODIR",
           "unlock": "pass a fleet dir: platformforge fleet <verb> <dir> "
                     "(see lab/fleets/acme for the format)"}


def _bundle(args) -> tuple | dict:
    path = getattr(args, "path", "")
    if not path or not Path(path).is_dir():
        return _NO_DIR
    data = load_fleet_dir(path)
    return fleet_from(data), graph_from_doc(data.get("graph")), data


def _snapshot(fleet, data) -> FleetSnapshot:
    obs = [MemberObservation(**{k: v for k, v in o.items()
                                if k in MemberObservation.__dataclass_fields__})
           for o in (data.get("capacity") or {}).get(
               "observations",
               (data.get("fleet") or {}).get("observations", []))]
    return FleetSnapshot(fleet_id=fleet.fleet_id,
                         member_observations=obs)


def cmd_fleet(args) -> dict[str, Any]:
    b = _bundle(args)
    if isinstance(b, dict):
        return b
    fleet, graph, data = b
    sub = args.fleet_cmd

    if sub == "list":
        return {"fleet_id": fleet.fleet_id,
                "members": [m.to_dict() for m in fleet.members],
                "count": len(fleet.members)}
    if sub in ("status", "coverage"):
        return _snapshot(fleet, data).to_dict()
    if sub == "graph":
        from platformforge.fleet.orggraph import project_fleet
        g = project_fleet(fleet, {"fleet": graph})
        return {"nodes": len(g.nodes), "edges": len(g.edges),
                "layers": sorted({n.attrs.get("layer") for n in g.nodes.values()
                                  if n.attrs.get("layer")}),
                "note": "org projection — organizational edges are not "
                        "blast radius"}
    if sub == "risks":
        from platformforge.fleet.query import FLEET_QUESTIONS, fleet_query
        if args.question:
            if args.question not in FLEET_QUESTIONS:
                return {"refusal": "PF-FLEET-QUESTION",
                        "unlock": f"questions: {sorted(FLEET_QUESTIONS)}"}
            return fleet_query(graph, args.question)
        return {q: fleet_query(graph, q) for q in FLEET_QUESTIONS}
    if sub == "costs":
        from platformforge.analytics.finops_v4 import (
            anomalies,
            cost_hierarchy,
            cost_trend,
            idle_resources,
            rightsizing,
        )
        c = data.get("costs") or {}
        return {"hierarchy": cost_hierarchy(c.get("allocations", [])),
                "trend": cost_trend(c.get("points", [])),
                "anomalies": anomalies(c.get("points", [])),
                "idle": idle_resources(c.get("resources", [])),
                "rightsizing": [x for x in (rightsizing(w) for w in
                                          c.get("workloads", [])) if x]}
    if sub == "capacity":
        from platformforge.analytics.capacity import capacity_risk
        from platformforge.optimize.scan import capacity_snapshots
        cap = data.get("capacity") or {}
        meta = {m["member_id"]: m for m in cap.get("members", [])}
        return {"members": [
            capacity_risk(
                snap, criticality=meta.get(mid, {}).get("criticality"),
                autoscaling=meta.get(mid, {}).get("autoscaling"),
                failure_domains=meta.get(mid, {}).get("failure_domains"))
            for mid, snap in capacity_snapshots(cap).items()],
            "gpu_pools": cap.get("gpu_pools", []),
            "note": "unknown headroom is reported, never zeroed"}
    if sub in ("incidents", "operations", "drift"):
        from platformforge.analytics.opsanalytics import (
            fleet_timeline,
            incident_patterns,
            operation_hotspots,
            operation_metrics,
            remediation_recurrence,
        )
        ev = data.get("events") or {}
        if sub == "incidents":
            return {"patterns": incident_patterns(ev.get("incident", [])),
                    "timeline": fleet_timeline(ev, limit=args.limit)}
        if sub == "operations":
            return {"metrics": operation_metrics(ev.get("operation", [])),
                    "hotspots": operation_hotspots(ev.get("operation", [])),
                    "recurrence": remediation_recurrence(
                        ev.get("remediation", [])),
                    "timeline": fleet_timeline(ev, limit=args.limit)}
        from platformforge.analytics.history import HistoryEngine
        eng = HistoryEngine()
        for k, evs in ev.items():
            eng.ingest_events(k, evs, "cli")
        win = args.window or "90d"
        return {"window": win,
                "patterns": [p.to_dict() for p in eng.patterns(win)]}
    if sub == "golden-path":
        from platformforge.analytics.goldenpath import (
            golden_path_analytics,
            golden_path_recommendations,
        )
        r = data.get("requests") or {}
        a = golden_path_analytics(r.get("requests", []),
                                  outcomes=r.get("outcomes", []),
                                  escapes=r.get("escapes", []))
        return {**a, "recommendations": golden_path_recommendations(a)}
    if sub == "policies":
        from platformforge.analytics.policyintel import (
            false_positive_candidates,
            policy_metrics,
            policy_recommendations,
        )
        p = data.get("policies") or {}
        m = policy_metrics(p.get("decisions", []),
                           exceptions=p.get("exceptions", []),
                           overrides=p.get("overrides", []))
        fp = false_positive_candidates(m, p.get("outcomes", {}))
        return {"metrics": m, "false_positive_candidates": fp,
                "recommendations": policy_recommendations(m, fp),
                "note": "review-required — policies never auto-change"}
    if sub == "recommendations":
        return _optimize_scan(fleet, graph, data).portfolio(
            top=args.limit or 10)
    if sub == "report":
        return _fleet_report(fleet, graph, data, args)
    return {"error": f"unknown fleet verb {sub}"}


def _fleet_report(fleet, graph, data, args) -> dict[str, Any]:
    """North-star receipt (§1/§303): how is the fleet behaving, where
    are the biggest problems, where to invest — every claim cited."""
    from platformforge.fleet.query import FLEET_QUESTIONS, fleet_query
    snap = _snapshot(fleet, data)
    eng = _optimize_scan(fleet, graph, data)
    portfolio = eng.portfolio(top=args.limit or 5)

    # per-dimension rollup — each row keeps its evidence
    risks = {q: fleet_query(graph, q) for q in FLEET_QUESTIONS}
    dimensions: dict[str, dict[str, Any]] = {}
    _dim_questions = {
        "security": ("public-services", "wildcard-iam"),
        "standardization": ("unsupported-k8s", "unowned"),
        "reliability": ("no-slo", "cross-env-deps"),
        "platform-product": ("outside-golden-path",),
        "cost": ("idle-high-cost",),
    }
    for dim, qs in _dim_questions.items():
        items = [i for q in qs for i in risks[q]["items"]]
        dimensions[dim] = {
            "findings": len(items),
            "nodes": sorted({i["node_id"] for i in items}),
            "evidence": [f for i in items
                         for f in (i.get("fact_ids") or [])][:8],
            "confidence": "low" if snap.coverage < 0.8 else "medium"}

    invest = [
        {"recommendation_id": r["recommendation_id"], "type": r["type"],
         "confidence": r["confidence"],
         "estimated_savings": r.get("estimated_savings"),
         "savings_unit": r.get("savings_unit"),
         "evidence": r.get("evidence", []),
         "priority": r.get("priority", {}).get("rank_score")}
        for r in portfolio["top"]]
    return {
        "schema": "platformforge/fleet-report/v1",
        "fleet_id": fleet.fleet_id,
        "coverage": {"ratio": snap.coverage_ratio,
                     "min_member": snap.coverage,
                     "note": "fleet conclusions bounded by coverage — "
                             "partial data never completes"},
        "dimensions": dimensions,
        "portfolio": {"opportunities": portfolio["total_opportunities"],
                      "promoted": portfolio["promoted"],
                      "suppressed": portfolio["suppressed"]},
        "invest_next": invest,
        "verdict": ("evidence-backed answers; suppressed opportunities "
                    "kept visible; optimization ends at ChangeIntent"),
        "limitations": [
            "deterministic aggregates — no ML claims",
            "correlation is not causality",
            "coverage < 1 bounds every conclusion"]}


def _optimize_scan(fleet, graph, data):
    from platformforge.analytics.models import AnalyticsDataQuality
    from platformforge.optimize.engine import OptimizationEngine
    from platformforge.optimize.scan import scan_fleet
    snap = _snapshot(fleet, data)
    ev = data.get("events") or {}
    # fleet coverage caps recommendation confidence via dq (§251) —
    # it is NOT per-opportunity coverage (a fully-observed member in a
    # partially-covered fleet can still promote, at capped confidence)
    dq = AnalyticsDataQuality(
        coverage=snap.coverage,
        sample_size=sum(len(v) for v in ev.values()))
    eng = OptimizationEngine(dq)
    scan_fleet(data, graph, engine=eng)
    return eng


def cmd_optimize(args) -> dict[str, Any]:
    b = _bundle(args)
    if isinstance(b, dict):
        return b
    fleet, graph, data = b
    eng = _optimize_scan(fleet, graph, data)
    sub = args.optimize_cmd

    if sub == "scan":
        return {"opportunities": [o.to_dict()
                                  for o in eng.opportunities()],
                "count": len(eng.opportunities())}
    if sub == "list":
        return {"recommendations": [r.to_dict()
                                    for r in eng.recommendations()]}
    if sub == "portfolio":
        return eng.portfolio(top=args.limit or 10)
    if sub == "explain":
        for r in eng.recommendations():
            if r.recommendation_id == args.id:
                return r.to_dict()
        return {"refusal": "PF-OPT-NOTFOUND",
                "unlock": "platformforge optimize list <dir>"}
    if sub == "plan":
        # §303 — the ONLY bridge; emits a ChangeIntent doc, never runs it
        from platformforge.optimize.engine import OptimizationEngine
        for r in eng.recommendations():
            if r.recommendation_id == args.id:
                ci = OptimizationEngine.plan(r).to_dict()
                out = {"change_intent": ci,
                       "note": "hand to the ops pipeline — plan does not "
                               "execute; policy/approval/verify still apply"}
                if args.out:
                    import yaml
                    Path(args.out).write_text(yaml.safe_dump(
                        ci, sort_keys=False))
                    out["written"] = args.out
                    out["next"] = ("ops intent --intent " + args.out +
                                   " → ops plan → governed pipeline")
                return out
        return {"refusal": "PF-OPT-NOTFOUND",
                "unlock": "platformforge optimize list <dir>"}
    return {"error": f"unknown optimize verb {sub}"}


def cmd_analytics(args) -> dict[str, Any]:
    b = _bundle(args)
    if isinstance(b, dict):
        return b
    fleet, graph, data = b
    sub = args.analytics_cmd

    if sub == "summary":
        from platformforge.analytics.opsanalytics import fleet_timeline
        snap = _snapshot(fleet, data)
        ev = data.get("events") or {}
        return {"fleet_id": fleet.fleet_id,
                "coverage": {"ratio": snap.coverage_ratio,
                             "min_member": snap.coverage},
                "sources": {k: len(v) for k, v in ev.items()},
                "timeline_events": len(fleet_timeline(ev)),
                "note": "deterministic aggregates only — no ML claims"}
    if sub == "metric":
        return _metric(args.id, fleet, graph, data)
    if sub == "maturity":
        from platformforge.analytics.measurement import maturity_assessment
        return maturity_assessment(_signals(fleet, graph, data))
    return {"error": f"unknown analytics verb {sub}"}


def _signals(fleet, graph, data) -> dict[str, dict[str, Any]]:
    """Deterministic maturity signals from the bundle (§44–48) —
    missing inputs stay `unknown`, never zero."""
    from platformforge.analytics.goldenpath import golden_path_analytics
    ev = data.get("events") or {}
    req = data.get("requests") or {}
    gp = golden_path_analytics(req.get("requests", []),
                               outcomes=req.get("outcomes", []),
                               escapes=req.get("escapes", []))
    total = sum(p["requests"] for p in gp.get("paths", {}).values())
    succeeded = sum(p["successful"] for p in gp.get("paths", {}).values())
    ratio = round(succeeded / total, 3) if total else None
    return {
        "adoption": {"value": ratio,
                     "sample_size": total,
                     "evidence": ["golden-path requests"]},
        "self_service": {"value": None, "sample_size": 0,
                         "evidence": ["requires ticketing data — unknown"]},
        "reliability": {"value": None,
                        "sample_size": len(ev.get("incident", [])),
                        "evidence": ["incident stream"]},
        "cost_efficiency": {"value": None, "sample_size": 0,
                            "evidence": ["see fleet costs"]},
    }


def _metric(metric_id, fleet, graph, data) -> dict[str, Any]:
    from platformforge.analytics.finops_v4 import cost_hierarchy
    from platformforge.analytics.goldenpath import golden_path_analytics
    from platformforge.analytics.models import PlatformMetric
    req = data.get("requests") or {}
    costs = data.get("costs") or {}

    if metric_id == "gp-adoption":
        gp = golden_path_analytics(req.get("requests", []),
                                   outcomes=req.get("outcomes", []),
                                   escapes=req.get("escapes", []))
        total = sum(p["requests"] for p in gp.get("paths", {}).values())
        done = sum(p["successful"] for p in gp.get("paths", {}).values())
        return PlatformMetric(
            metric_id="gp-adoption", dimension="adoption",
            scope={"fleet": fleet.fleet_id},
            value=(round(done / total, 3) if total else None),
            unit="ratio", source="golden-path-analytics",
            evidence=["golden-path request stream"],
            completeness=1.0 if total else None).to_dict()
    if metric_id == "unallocated-cost":
        tree = cost_hierarchy(costs.get("allocations", []))
        return PlatformMetric(
            metric_id="unallocated-cost", dimension="cost-efficiency",
            scope={"fleet": fleet.fleet_id}, value=tree["unallocated"],
            unit="cost_monthly", source="cost-hierarchy",
            evidence=["cost allocations"],
            completeness=(1 - tree["unallocated_ratio"])
            if tree["unallocated_ratio"] is not None else None).to_dict()
    return {"refusal": "PF-ANALYTICS-METRIC",
            "unlock": "known metrics: gp-adoption, unallocated-cost"}


def _load_yaml(path: str, refusal: str, unlock: str) -> Any:
    import yaml
    if not path or not Path(path).exists():
        return {"refusal": refusal, "unlock": unlock}
    doc = yaml.safe_load(Path(path).read_text())
    return doc


def cmd_ai(args) -> dict[str, Any]:
    from platformforge.aiplat.models import (
        GPUCapacity,
        ai_capacity_risk,
        ai_unit_economics,
        detect_ai_workloads,
    )
    sub = args.ai_cmd
    if sub == "workloads":
        doc = _load_yaml(args.path, "PF-AI-NOFILE",
                         "platformforge ai workloads <resources.yaml>")
        if isinstance(doc, dict) and "refusal" in doc:
            return doc
        res = doc if isinstance(doc, list) else \
            doc.get("k8s_resources", doc.get("resources", []))
        return {"workloads": detect_ai_workloads(res)}
    if sub == "gpu":
        doc = _load_yaml(args.path, "PF-AI-NOFILE",
                         "platformforge ai gpu <capacity.yaml>")
        if isinstance(doc, dict) and "refusal" in doc:
            return doc
        pools = [GPUCapacity(**{k: v for k, v in p.items()
                                if k in GPUCapacity.__dataclass_fields__})
                 for p in doc.get("gpu_pools", [])]
        return ai_capacity_risk(pools)
    if sub == "economics":
        import json
        denoms = json.loads(args.denominators) if args.denominators else {}
        return ai_unit_economics(args.cost,
                                 tokens=denoms.get("tokens"),
                                 inferences=denoms.get("inferences"),
                                 gpu_hours=denoms.get("gpu_hours"))
    return {"error": f"unknown ai verb {sub}"}


def cmd_federation(args) -> dict[str, Any]:
    from platformforge.federation.node import (
        FederationPolicy,
        NodeManifest,
        export_summary,
        federated_query,
    )
    sub = args.federation_cmd
    if sub == "manifest":
        caps = [c.strip() for c in (args.capabilities or "").split(",")
                if c.strip()]
        return NodeManifest(
            node_id=args.node_id or "node", capabilities=caps,
            data_freshness=args.freshness or "unknown").to_dict()
    if sub == "export":
        payload = _load_yaml(args.path, "PF-FED-NOFILE",
                             "platformforge federation export <payload.yaml> "
                             "--classification <class>")
        if isinstance(payload, dict) and "refusal" in payload:
            return payload
        node = NodeManifest(node_id=args.node_id or "node")
        policy = None
        if args.manifest:
            md = _load_yaml(args.manifest, "PF-FED-NOFILE",
                            "--manifest <manifest.yaml>")
            if isinstance(md, dict) and "refusal" in md:
                return md
            node.node_id = md.get("node_id", node.node_id)
            if md.get("export_policy"):
                policy = FederationPolicy(rules=md["export_policy"])
        return export_summary(node, payload,
                              args.classification or "internal",
                              policy=policy)
    if sub == "query":
        # each --nodes dir is a fleet dir; node answers locally (E9 —
        # no authority or credential ever crosses the boundary)
        from platformforge.fleet.query import FLEET_QUESTIONS, fleet_query
        nodes, graphs = [], []
        for i, d in enumerate(args.nodes or []):
            if not Path(d).is_dir():
                continue
            data = load_fleet_dir(d)
            nodes.append(NodeManifest(node_id=Path(d).name or f"n{i}"))
            graphs.append(graph_from_doc(data.get("graph")))
        if not nodes:
            return {"refusal": "PF-FED-NONODES",
                    "unlock": "--nodes <fleet-dir> [<fleet-dir>...]"}
        question = args.question or args.path
        if question not in FLEET_QUESTIONS:
            return {"refusal": "PF-FED-QUESTION",
                    "unlock": f"questions: {sorted(FLEET_QUESTIONS)}"}

        def _local(node, question):
            idx = next(i for i, n in enumerate(nodes)
                       if n.node_id == node.node_id)
            r = fleet_query(graphs[idx], question)
            return {"answered": True, "count": r["count"],
                    "items": r["items"][: args.limit or 20]}
        return federated_query(nodes, _local, question)
    return {"error": f"unknown federation verb {sub}"}
