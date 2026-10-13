"""§104 change review — composes the sandbox delta into the full review
pipeline: diff → planned graph → blast → IAM/networking/availability/
cost/security/SLO → risk → recommended validation. Read-only; review
never applies.
"""

from __future__ import annotations

from typing import Any

from platformforge.models import Fact
from platformforge.risk.engine import assess_change
from platformforge.rules import RuleEngine, load_catalog
from platformforge.sandbox.env import sandbox_analyze


def _findings(facts, catalog_dirs) -> list[dict[str, Any]]:
    rules = load_catalog(*catalog_dirs)
    objs = [Fact.from_dict(f) if isinstance(f, dict) else f for f in facts]
    findings, _skipped = RuleEngine(rules).evaluate(objs)
    return [f.to_dict() for f in findings]


def review_change(repo: str | Any,
                  patch: str | None = None,
                  files: dict[str, str] | None = None,
                  signals: dict[str, Any] | None = None,
                  catalog_dirs=None) -> dict[str, Any]:
    """Run sandbox_analyze, then judge findings on the after-state and
    score the risk delta. Output is a review — never a decision."""
    if catalog_dirs is None:
        # resolve via data_path — a CWD-relative default yields an empty
        # catalog (zero-rule review) outside the repo checkout
        from platformforge.resources import data_path
        catalog_dirs = (data_path("rules", "catalog"),)
    run = sandbox_analyze(repo, patch=patch, files=files)
    if "refusal" in run:
        return run

    findings_before = _findings(run["before"]["facts"], catalog_dirs)
    findings_after = _findings(run["after"]["facts"], catalog_dirs)

    sem = run.get("semantic") or {}
    gdiff = sem.get("graph_diff") or {}
    blast = gdiff.get("blast_radius_delta") or {}

    # §104 dimensions — each is a named section, unknown when evidence is
    # missing rather than silently "clean"
    dims: dict[str, Any] = {
        "diff": {"facts_added": run["delta"]["facts_added"],
                 "facts_removed": run["delta"]["facts_removed"],
                 "kinds_changed": run["delta"]["fact_kinds_changed_count"]},
        "graph": {"nodes_added": sem.get("nodes_added"),
                  "nodes_removed": sem.get("nodes_removed"),
                  "exposure_added": sem.get("exposure_added"),
                  "security_edges_changed":
                      sem.get("security_edges_changed")},
        "blast_radius": {"changed_nodes": len(blast),
                         "worst": max((v["after"] for v in blast.values()),
                                      default=0)},
        "findings_delta": {
            "before": len(findings_before),
            "after": len(findings_after),
            "new": [f.get("rule_id") for f in findings_after
                    if f.get("rule_id") not in
                    {fb.get("rule_id") for fb in findings_before}],
            "resolved": [f.get("rule_id") for f in findings_before
                         if f.get("rule_id") not in
                         {fa.get("rule_id") for fa in findings_after}]},
    }
    signals_out = assess_change({
        "blast_radius": dims["blast_radius"]["worst"],
        "security_impact": bool(dims["findings_delta"]["new"]),
        "network_exposure": sem.get("exposure_added", False),
        **(signals or {})})
    dims["risk"] = signals_out
    dims["recommended_validation"] = _validation(dims)
    return {"review": dims,
            "note": "review only — apply/approve remain host-side"}


def _validation(dims: dict[str, Any]) -> list[str]:
    steps = ["re-run `platformforge judge` on the after-state"]
    if dims["graph"].get("exposure_added"):
        steps.append("manual network review — new exposure edge added")
    if dims["findings_delta"]["new"]:
        steps.append("fix new findings before approval")
    if dims["risk"].get("level") in ("high", "critical"):
        steps.append("require second approver + sandbox receipt")
    if dims["risk"].get("underreported"):
        steps.append("resolve unknown risk signals before sign-off")
    return steps
