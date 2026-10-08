"""Cycle 5 Phase N — fleet lab scenarios (§273–285).

A fleet scenario is a fixture (fleet + graphs + events + costs +
capacity + requests + policies) evaluated by deterministic checks —
the same analytics used by the real CLI. `kind: fleet` in the
scenario YAML. Every verdict is evidence-cited; coverage is always
part of the answer.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from platformforge.fleet.models import Fleet
from platformforge.fleet.query import fleet_query
from platformforge.graph.model import Edge, Graph, Node


def _load_fixture(fx: Path) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name in ("fleet", "graph", "events", "costs", "capacity",
                 "requests", "policies"):
        p = fx / f"{name}.yaml"
        out[name] = yaml.safe_load(p.read_text()) if p.exists() else None
    return out


def _graph_from_doc(doc: dict[str, Any] | None) -> Graph:
    g = Graph()
    for n in (doc or {}).get("nodes", []):
        g.add_node(Node.make(n["kind"], n["id"], attrs=n.get("attrs", {}),
                             fact_ids=n.get("fact_ids", ())))
    for e in (doc or {}).get("edges", []):
        src_id = e["src_id"]
        dst_id = e["dst_id"]
        if src_id not in g.nodes:
            kind, _, label = src_id.partition("/")
            try:
                g.add_node(Node.make(kind, label or src_id))
            except ValueError:
                continue
        if dst_id not in g.nodes:
            kind, _, label = dst_id.partition("/")
            try:
                g.add_node(Node.make(kind, label or dst_id))
            except ValueError:
                continue
        g.add_edge(Edge(src_id, dst_id, e["kind"],
                        provenance=e.get("provenance", "declared"),
                        source_fact_ids=tuple(e.get("fact_ids", ()))))
    return g


def run_fleet_scenario(scenario_dir) -> dict[str, Any]:
    """`scenario_dir` holds expected.yaml (checks) + fixture/ (data)."""
    d = Path(scenario_dir)
    doc = yaml.safe_load((d / "expected.yaml").read_text())
    # shared fleet fixtures live in lab/fleets/<name>; per-scenario
    # fixture/ overrides file-by-file (§274 — one fleet, many questions)
    shared = doc.get("shared_fixture")
    data: dict[str, Any] = {}
    if shared:
        from platformforge.resources import data_path
        data = _load_fixture(data_path() / shared)
    local = d / "fixture"
    if local.is_dir():
        for k, v in _load_fixture(local).items():
            if v is not None:
                data[k] = v
    fx = d
    checks: list[str] = []
    failures: list[str] = []
    results: dict[str, Any] = {}

    fleet_doc = data.get("fleet") or {}
    fleet = Fleet.from_dict(fleet_doc) if fleet_doc.get("fleet_id") \
        else Fleet(fleet_id=fleet_doc.get("fleet_id", "lab"))
    graph = _graph_from_doc(data.get("graph"))
    events = data.get("events") or {}
    costs = data.get("costs") or {}
    capacity = data.get("capacity") or {}
    requests = data.get("requests") or {}
    policies = data.get("policies") or {}

    for chk in doc.get("checks", []):
        kind, expect = next(iter(chk.items()))
        checks.append(kind)
        r = _run_check(kind, expect, fleet, graph, events, costs,
                       capacity, requests, policies, data)
        results[kind] = r
        failures.extend(r.get("failures", []))
    return {"scenario": fx.name, "checks": checks, "results": results,
            "failures": failures,
            "verdict": "pass" if not failures else "fail"}


def _patterns_at(eng, window: str, now) -> list:
    """patterns() against a fixed lab clock."""
    from platformforge.analytics.history import WINDOWS
    from platformforge.analytics.models import HistoricalPattern, confidence_for_support
    since = now - WINDOWS.get(window, WINDOWS["90d"])
    groups: dict[tuple, list] = {}
    for e in eng._events:
        if since <= e.ts <= now:
            k = (e.subject, e.kind, e.outcome)
            groups.setdefault(k, []).append(e)
    return [HistoricalPattern(
        pattern_id=f"{kind}:{subj}:{outcome}", window=window,
        support=len(evs), sample_size=len(evs),
        confidence=confidence_for_support(len(evs)),
        scope={"subject": subj},
        limitations=["correlation is not causality"])
        for (subj, kind, outcome), evs in groups.items() if len(evs) >= 2]


def _expect_eq(name: str, got, want, failures: list[str]) -> None:
    if want is not None and got != want:
        failures.append(f"{name}: expected {want!r}, got {got!r}")


def _expect_min(name: str, got, want, failures: list[str]) -> None:
    if want is not None and not (got or 0) >= want:
        failures.append(f"{name}: expected >={want}, got {got}")


def _run_check(kind: str, expect: dict[str, Any], fleet, graph, events,
               costs, capacity, requests, policies,
               data) -> dict[str, Any]:
    f: list[str] = []
    out: dict[str, Any] = {"failures": f}

    if kind == "fleet_query":
        r = fleet_query(graph, expect["question"])
        _expect_min("count", r["count"], expect.get("min_count"), f)
        if expect.get("node_ids"):
            missing = set(expect["node_ids"]) - \
                {i["node_id"] for i in r["items"]}
            if missing:
                f.append(f"missing nodes: {sorted(missing)}")
        out["result"] = r

    elif kind == "history_pattern":
        from platformforge.analytics.history import HistoryEngine
        from platformforge.live.models import parse_ts
        eng = HistoryEngine()
        for k, evs in events.items():
            eng.ingest_events(k, evs, "lab")
        # deterministic lab clock — newest event is "now" so fixtures
        # never age out of their own windows
        stamps = [parse_ts(str(e.get("ts", ""))) for evs in
                  events.values() for e in evs]
        now = max((s for s in stamps if s), default=None)
        win = expect.get("window", "90d")
        pats = eng.patterns(win) if now is None else \
            _patterns_at(eng, win, now)
        _expect_min("patterns", len(pats), expect.get("min_support"), f)
        if expect.get("max_confidence"):
            order = {"low": 0, "medium": 1, "high": 2}
            for p in pats:
                if order[p.confidence] > order[expect["max_confidence"]]:
                    f.append(f"confidence {p.confidence} exceeds cap "
                             f"{expect['max_confidence']}")
        out["result"] = [p.to_dict() for p in pats]

    elif kind == "policy_analytics":
        from platformforge.analytics.policyintel import (
            false_positive_candidates,
            policy_metrics,
            policy_recommendations,
        )
        m = policy_metrics(policies.get("decisions", []),
                           exceptions=policies.get("exceptions", []),
                           overrides=policies.get("overrides", []))
        fps = false_positive_candidates(m, policies.get("outcomes", {}))
        recs = policy_recommendations(m, fps)
        if expect.get("policy"):
            pm = m.get(expect["policy"], {})
            for k, v in expect.get("metrics", {}).items():
                _expect_eq(f"policy.{k}", pm.get(k), v, f)
        _expect_min("fp_candidates", len(fps),
                    expect.get("min_fp"), f)
        _expect_min("recommendations", len(recs),
                    expect.get("min_recs"), f)
        if expect.get("no_auto_apply") and \
                any(r.get("executes") for r in recs):
            f.append("recommendation marked executes")
        out["result"] = {"metrics": m, "fp": fps, "recs": recs}

    elif kind == "golden_path":
        from platformforge.analytics.goldenpath import golden_path_analytics, golden_path_recommendations
        a = golden_path_analytics(requests.get("requests", []),
                                  outcomes=requests.get("outcomes", []),
                                  escapes=requests.get("escapes", []))
        pa = a["paths"].get(expect.get("path", ""), {})
        for k, v in expect.get("expect", {}).items():
            _expect_eq(f"gp.{k}", pa.get(k), v, f)
        if expect.get("escape_reason") and \
                expect["escape_reason"] not in pa.get(
                        "escape_reasons", {}):
            f.append(f"escape reason {expect['escape_reason']} "
                     "not observed")
        recs = golden_path_recommendations(a)
        _expect_min("recs", len(recs), expect.get("min_recs"), f)
        out["result"] = a

    elif kind == "cost":
        from platformforge.analytics.finops_v4 import cost_hierarchy, cost_trend, idle_resources, rightsizing
        if "hierarchy" in expect:
            h = cost_hierarchy(costs.get("allocations", []))
            _expect_min("unallocated", h["unallocated"],
                        expect["hierarchy"].get("min_unallocated"), f)
            out["result"] = h
        if "rightsizing" in expect:
            hits = [rightsizing(w) for w in costs.get("workloads", [])]
            hits = [h for h in hits if h]
            _expect_min("rightsizing", len(hits),
                        expect["rightsizing"].get("min"), f)
            out["result"] = hits
        if "idle" in expect:
            idle = idle_resources(costs.get("resources", []))
            _expect_min("idle", len(idle), expect["idle"].get("min"), f)
            if any(i["deletable"] for i in idle):
                f.append("idle marked deletable")
            out["result"] = idle
        if "trend" in expect:
            t = cost_trend(costs.get("points", []))
            _expect_eq("trend", t["trend"],
                       expect["trend"].get("direction"), f)
            out["result"] = t

    elif kind == "capacity":
        from platformforge.analytics.capacity import CapacityDimension, CapacitySnapshot, capacity_risk
        snaps = {}
        for m in capacity.get("members", []):
            snaps[m["member_id"]] = CapacitySnapshot(
                member_id=m["member_id"],
                dimensions=[CapacityDimension(
                    d["name"], d.get("used"), d.get("capacity"),
                    d.get("source", "observed"))
                    for d in m.get("dimensions", [])])
        member = expect.get("member")
        if member and member in snaps:
            risk = capacity_risk(
                snaps[member],
                criticality=expect.get("criticality"),
                failure_domains=expect.get("failure_domains"))
            _expect_eq("risk", risk["risk"], expect.get("expect_risk"), f)
            out["result"] = risk
        else:
            sats = {mid: s.saturation() for mid, s in snaps.items()}
            hot = [mid for mid, s in sats.items()
                   if s["saturated_dimensions"]]
            _expect_min("saturated", len(hot), expect.get("min_hot"), f)
            out["result"] = sats

    elif kind == "reliability":
        from platformforge.analytics.reliability import blast_concentration, build_profile, fleet_hotspots
        profiles = [build_profile(
            s["service"], events.get("incident", []) if s.get("all") else
            [i for i in events.get("incident", [])
             if i.get("service") == s["service"]],
            [c for c in events.get("deployment", [])
             if c.get("service") == s["service"]],
            [r for r in events.get("rollback", [])
             if r.get("service") == s["service"]])
            for s in expect.get("services",
                                [{"service": s} for s in {
                                    i.get("service") for i in
                                    events.get("incident", [])
                                    if i.get("service")}])]
        hot = fleet_hotspots(profiles)
        _expect_min("hotspots", len(hot), expect.get("min_hotspots"), f)
        if expect.get("blast"):
            conc = blast_concentration(graph)
            out["blast"] = conc
            _expect_min("centrality", len(conc),
                        expect["blast"].get("min"), f)
        out["result"] = hot

    elif kind == "operations":
        from platformforge.analytics.opsanalytics import (
            operation_hotspots,
            operation_metrics,
            remediation_recurrence,
        )
        ops = events.get("operation", [])
        m = operation_metrics(ops)
        hot = operation_hotspots(ops, expect.get("min_count", 3))
        rec = remediation_recurrence(events.get("remediation", []))
        for k, v in expect.get("metrics", {}).items():
            _expect_eq(f"ops.{k}", m.get(k), v, f)
        _expect_min("hotspots", len(hot), expect.get("min_hotspots"), f)
        _expect_min("recurrence", len(rec), expect.get("min_recurrence"),
                    f)
        if expect.get("no_auto_remediate") and \
                any(r.get("auto_remediate") for r in rec):
            f.append("auto_remediate true")
        out["result"] = {"metrics": m, "hotspots": hot,
                         "recurrence": rec}

    elif kind == "coverage":
        from platformforge.fleet.models import FleetSnapshot, MemberObservation
        obs = [MemberObservation(**o)
               for o in (data.get("capacity", {}) or {}).get(
                   "observations",
                   (data.get("fleet") or {}).get("observations", []))]
        snap = FleetSnapshot(fleet_id=fleet.fleet_id,
                             member_observations=obs)
        _expect_eq("ratio", snap.coverage_ratio,
                   expect.get("ratio"), f)
        if expect.get("max_coverage") is not None and \
           snap.coverage > expect["max_coverage"]:
            f.append(f"coverage {snap.coverage} exceeds cap "
                     f"{expect['max_coverage']}")
        out["result"] = snap.to_dict()

    elif kind == "federation":
        from platformforge.federation.node import NodeManifest, export_summary
        fed = data.get("fleet", {}).get("federation", {})
        node = NodeManifest(node_id=fed.get("node_id", "n1"),
                            capabilities=fed.get("capabilities", []))
        for exp in fed.get("exports", []):
            s = export_summary(node, exp.get("payload", {}),
                               exp.get("classification", "internal"))
            out.setdefault("exports", []).append(s)
        for i, exp in enumerate(expect.get("exports", [])):
            got = out["exports"][i] if i < len(out["exports"]) else {}
            _expect_eq("fed.action", got.get("action"),
                       exp.get("action"), f)

    elif kind == "ai":
        from platformforge.aiplat.models import ai_unit_economics, detect_ai_workloads
        w = detect_ai_workloads(capacity.get("k8s_resources", []))
        _expect_min("ai_workloads", len(w), expect.get("min_detected"), f)
        if "unit_economics" in expect:
            ue = ai_unit_economics(
                expect["unit_economics"].get("cost"),
                tokens=expect["unit_economics"].get("tokens"))
            _expect_eq("cost/token", ue.get("cost_per_1m_tokens",
                                            ue.get("tokens_metric")),
                       expect["unit_economics"].get("expect"), f)
            out["ue"] = ue
        out["result"] = w

    else:
        f.append(f"unknown check kind: {kind}")
    return out
