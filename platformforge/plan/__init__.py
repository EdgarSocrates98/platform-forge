"""Remediation planner (§7 `plan`) — findings → ordered change plan.

Steps are ordered by severity, then decomposed risk when a graph exists.
Each step carries its evidence and a rollback note; a step with no evidence
is refused rather than planned.
"""

from __future__ import annotations

from typing import Any

_SEV = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


def remediation_plan(findings: list[dict],
                     graph: Any | None = None,
                     facts: list[dict] | None = None) -> dict[str, Any]:
    violated = [f for f in findings if f.get("status") == "violated"]
    refused = [f.get("rule_id") for f in findings
               if f.get("status") == "violated" and not f.get("evidence")]

    facts_by_id = {f.get("fact_id"): f for f in facts or []}
    steps = []
    for f in violated:
        if not f.get("evidence"):
            continue
        blast_n = None
        if graph is not None:
            from platformforge.graph.query import blast_radius
            for e in f["evidence"]:
                nid = facts_by_id.get(e, {}).get("attrs", {}).get("node_id")
                if nid and nid in graph.nodes:
                    blast_n = max(blast_n or 0,
                                  len(blast_radius(graph, nid)["nodes"]))
        steps.append({"rule_id": f["rule_id"], "title": f.get("title"),
                      "severity": f.get("severity", "medium"),
                      "evidence": f["evidence"],
                      "remediation": f.get("remediation", ""),
                      "blast_size": blast_n,
                      "rollback": "revert the change that violates "
                                  f"{f['rule_id']}; verify with judge"})
    steps.sort(key=lambda s: (_SEV.get(s["severity"], 9),
                              -(s["blast_size"] or 0)))
    return {"plan": "platformforge.remediation/v1", "steps": steps,
            "counts": {"steps": len(steps), "refused": len(refused)},
            "refused": refused,
            "boundary": "plan is a proposal — apply lives host-side "
                        "(platform.change.core_read_only)"}
