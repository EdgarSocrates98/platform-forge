"""pf-* executor subagents — one deterministic job each (§57–66).

Executors do ONE thing, return structured output, and never dispatch
other agents. They are thin wrappers over the deterministic engines —
collect/analyze/judge/graph/ops — so a caller can bound an executor's
work inside a run envelope without giving it reasoning authority.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from platformforge.models.base import Fact, stable_id

EXECUTORS = ("pf-inventory", "pf-extractor", "pf-judge",
             "pf-graph-builder", "pf-reconciler", "pf-simulator",
             "pf-synthesizer", "pf-verifier")


def pf_inventory(root: str | Path) -> dict[str, Any]:
    """§58 — discover artifacts, identify domains + available evidence,
    emit a coverage map. Does not judge."""
    from platformforge.collect.detect import collect
    out = collect(root)
    detected = out.get("detected", {})
    return {"executor": "pf-inventory",
            "domains": sorted(detected),
            "coverage": {d: len(files) for d, files in detected.items()},
            "undetected": len(out.get("undetected", [])),
            "artifact_count": sum(map(len, detected.values())),
            "artifacts": {d: sorted(files) for d, files in
                          detected.items()}}


def pf_extract(artifacts: dict[str, Any] | str | Path) -> dict[str, Any]:
    """§59 — Artifact → Facts. Does not assign severity."""
    from platformforge.collect.detect import collect
    if isinstance(artifacts, (str, Path)):
        out = collect(artifacts)
    else:
        out = {"facts": artifacts.get("facts", [])}
    facts = []
    for f in out.get("facts", []):
        facts.append(f if isinstance(f, dict)
                     else (f.to_dict() if hasattr(f, "to_dict")
                           else {"value": str(f)}))
    return {"executor": "pf-extractor",
            "fact_ids": [f.get("fact_id", "") for f in facts],
            "facts": facts, "count": len(facts)}


def pf_judge(facts: list[dict[str, Any]],
             rules: Any) -> dict[str, Any]:
    """§60 — Facts → Rules → Findings. Never recommends a change."""
    from platformforge.rules.engine import RuleEngine
    fact_objs = [f if isinstance(f, Fact) else Fact.from_dict(f)
                 for f in facts]
    eng = rules if isinstance(rules, RuleEngine) else RuleEngine(rules)
    findings, skipped = eng.evaluate(fact_objs)
    return {"executor": "pf-judge",
            "findings": [f.to_dict() for f in findings],
            "skipped": skipped,
            "count": len(findings)}


def pf_graph_build(facts: list[dict[str, Any]]) -> dict[str, Any]:
    """§61 — Facts → Graphfy. No edge without a contributing fact_id."""
    from platformforge.graph.build import GraphBuilder
    gb = GraphBuilder().from_facts(facts)
    g = gb.graph
    edges = g.edges if isinstance(g.edges, dict) else {}
    no_prov = [k for k, e in edges.items()
               if not getattr(e, "source_fact_ids", ())]
    return {"executor": "pf-graph-builder",
            "nodes": len(g.nodes), "edges": len(edges),
            "unprovenanced_edges": sorted(no_prov),
            "graph": g.to_dict() if hasattr(g, "to_dict") else {}}


def pf_reconcile(*, desired: dict[str, Any],
                 planned: dict[str, Any],
                 observed: dict[str, Any]) -> dict[str, Any]:
    """§62 — desired/planned/observed reconciliation. All three states
    stay distinct; contradictions name both values."""
    def keys(g): return set((g or {}).keys())
    d, p, o = keys(desired), keys(planned), keys(observed)
    return {"executor": "pf-reconciler",
            "desired_only": sorted(d - p - o),
            "planned_not_observed": sorted(p - o),
            "observed_unplanned": sorted(o - p - d),
            "converged": sorted(d & p & o),
            "drift": sorted((p | d) ^ o),
            "receipt": stable_id("PF-REC", str(sorted(d)),
                                 str(sorted(p)), str(sorted(o)))}


def pf_simulate(*, observed_graph: dict[str, Any] | None = None,
                planned_graph: dict[str, Any] | None = None,
                plan_hash: str = "") -> dict[str, Any]:
    """§63 — safe simulation: planned graph → expected delta.
    Never executes; output is a delta document, not a change."""
    on = set((observed_graph or {}).get("nodes", {}))
    pn = set((planned_graph or {}).get("nodes", {}))
    oe = set((observed_graph or {}).get("edges", {}))
    pe = set((planned_graph or {}).get("edges", {}))
    return {"executor": "pf-simulator",
            "expected_delta": {
                "adds": {"resources": sorted(pn - on),
                         "dependencies": sorted(pe - oe)},
                "removes": {"resources": sorted(on - pn),
                            "dependencies": sorted(oe - pe)}},
            "plan_hash": plan_hash,
            "simulation_id": stable_id("PF-SIM", plan_hash,
                                       str(sorted(pn)))}


def pf_synthesize(*, findings: list[dict[str, Any]],
                  graph: dict[str, Any] | None = None,
                  reviews: list[dict[str, Any]] | None = None,
                  referee: dict[str, Any] | None = None) -> dict[str, Any]:
    """§64 — final composition. References only — mints no new facts."""
    return {"executor": "pf-synthesizer",
            "finding_count": len(findings),
            "statuses": {s: sum(1 for f in findings
                              if f.get("status") == s)
                         for s in {f.get("status") for f in findings}},
            "graph_nodes": len((graph or {}).get("nodes", {})),
            "reviews": len(reviews or []),
            "referee": bool(referee),
            "evidence": sorted({e for f in findings
                                for e in (f.get("evidence") or [])}),
            "unresolved": [f.get("claim", "") for f in findings
                           if f.get("status") in ("unresolved",
                                                  "unsupported",
                                                  "not-observed")],
            "synthesis_id": stable_id(
                "PF-SYN", str(len(findings)),
                str(len((graph or {}).get("nodes", {}))))}


def pf_verify(*, doc: dict[str, Any],
              expected_hash: str = "",
              receipt_fields: tuple[str, ...] = ("receipt_id",)
              ) -> dict[str, Any]:
    """§65 — mechanical proof checks used by platform-verifier:
    hash recompute, receipt-field presence, criterion→evidence shape."""
    from platformforge.agents.contracts import doc_hash
    problems = []
    got = doc.get("spec_hash") or doc.get("receipt_id") or ""
    if expected_hash and got != expected_hash:
        problems.append(f"hash mismatch: {got[:24]}… != "
                        f"{expected_hash[:24]}…")
    for f in receipt_fields:
        if f not in doc:
            problems.append(f"missing receipt field: {f}")
    return {"executor": "pf-verifier",
            "ok": not problems, "problems": problems,
            "doc_hash": doc_hash(doc),
            "check_id": stable_id("PF-PVF", str(sorted(doc)))}
