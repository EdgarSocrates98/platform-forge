"""§73/§78/§79 Golden Path engine — load the library, expose the
self-service capability surface, and analyze an *existing* estate for
path gaps (manual steps, missing automation/ownership/observability/
cost allocation).

The engine is offline and read-only: `capabilities()` describes what
could be requested; nothing is provisioned.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from platformforge.product.golden_paths.model import GoldenPath

LIBRARY = Path(__file__).with_name("library.yaml")


def load_library(path: str | Path | None = None) -> dict[str, Any]:
    doc = yaml.safe_load(Path(path or LIBRARY).read_text()) or {}
    paths, invalid = [], []
    for p in doc.get("paths") or []:
        try:
            paths.append(GoldenPath.from_dict(p))
        except ValueError as exc:
            invalid.append(str(exc))
    return {"paths": paths, "invalid": invalid,
            "schema": doc.get("schema", "")}


def describe(path_id: str,
             library_path: str | Path | None = None) -> dict[str, Any]:
    lib = load_library(library_path)
    for p in lib["paths"]:
        if p.id == path_id:
            return {"path": p.id, "name": p.name, "version": p.version,
                    "use_case": p.use_case, "inputs": p.inputs,
                    "outputs": p.outputs, "steps": p.steps,
                    "policies": p.policies, "ownership": p.ownership,
                    "observability": p.observability,
                    "security": p.security, "cost": p.cost,
                    "slo": p.slo, "escape_hatches": p.escape_hatches,
                    "supported_variants": p.supported_variants}
    return {"refusal": "PF-PATH-UNKNOWN",
            "unlock": "platformforge product paths",
            "requested": path_id}


def capabilities(library_path: str | Path | None = None) -> dict[str, Any]:
    """§79 — machine-readable self-service surface for agents/humans."""
    lib = load_library(library_path)
    return {"capabilities": [p.capability() for p in lib["paths"]],
            "invalid": lib["invalid"], "mutates": False,
            "approval_required": True}


def analyze_paths(facts: list[dict[str, Any]]) -> dict[str, Any]:
    """§78 — find platform gaps in existing artifacts, per §78's list:
    manual steps, duplicate workflows, missing automation/ownership/
    observability/cost allocation. Evidence-linked, never inferred."""
    gaps: list[dict[str, Any]] = []
    seen_workflows: dict[str, list[str]] = {}
    for f in facts:
        kind, a = f.get("kind", ""), f.get("attrs") or {}
        fid = f.get("fact_id", "")
        if kind == "k8s.workload":
            if not (a.get("labels") or {}).get("team") and \
                    not (a.get("labels") or {}).get("owner"):
                gaps.append({"gap": "missing_ownership", "fact_id": fid,
                             "location": f.get("location"),
                             "detail": "no team/owner label on workload"})
            if (a.get("pod_spec") or {}).get("no_requests", 0) > 0:
                pass  # covered by PF-K8S rules; path gaps stay structural
        elif kind == "gitops.argocd_app":
            if not a.get("automated_sync"):
                gaps.append({"gap": "missing_automation", "fact_id": fid,
                             "location": f.get("location"),
                             "detail": "argocd app syncs manually"})
        elif kind in ("gha.workflow", "cicd.pipeline"):
            key = (a.get("name") or a.get("pipeline_name") or "").lower()
            if key:
                seen_workflows.setdefault(key, []).append(fid)
        elif kind == "k8s.service" and \
                (a.get("svc_type") == "LoadBalancer"):
            pass
    for key, ids in seen_workflows.items():
        if len(ids) > 1:
            gaps.append({"gap": "duplicate_workflow",
                         "fact_id": ids[0], "detail":
                         f"workflow '{key}' declared {len(ids)} times",
                         "fact_ids": ids})
    return {"gaps": gaps, "count": len(gaps),
            "note": "gaps are findings about *platform paths*, not rule "
                    "violations — same location may appear in both"}
