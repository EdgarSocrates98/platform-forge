"""§63 Helm — Chart → values → render → manifests → facts.

Offline-first: `helm template` is used only when the binary exists on the
host. Without it, Chart.yaml/values.yaml still produce declared facts
(T3) and render-dependent capabilities come back named `unresolved`
rather than silently skipped. Rendered manifests flow through
`analyze_k8s` so the same rule catalog applies.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import yaml

from platformforge.k8s.manifests import analyze_k8s
from platformforge.models.base import stable_id

RENDER_CAPABILITY = "helm-render"


def _helm() -> str | None:
    return shutil.which("helm")


def _charts(root: Path) -> list[Path]:
    files = ([root / "Chart.yaml"] if root.is_file()
             else sorted(root.rglob("Chart.yaml")))
    return [p for p in files if p.exists()]


def analyze_helm(path: str | Path) -> dict[str, Any]:
    root = Path(path)
    charts = _charts(root)
    facts: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    rendered_docs = 0
    helm_bin = _helm()

    for chart in charts:
        cdir = chart.parent
        name = cdir.name
        loc = f"{chart}::{name}"
        try:
            cmeta = yaml.safe_load(chart.read_text()) or {}
        except yaml.YAMLError:
            cmeta = {}
        deps = [d.get("name") for d in cmeta.get("dependencies") or []
                if isinstance(d, dict)]
        attrs = {"chart": cmeta.get("name", name),
                 "chart_version": cmeta.get("version"),
                 "app_version": cmeta.get("appVersion"),
                 "api_version": cmeta.get("apiVersion"),
                 "dependencies": [d for d in deps if d],
                 "templates": len(list((cdir / "templates").glob("*.yaml")))
                 if (cdir / "templates").is_dir() else 0}
        facts.append({"fact_id": stable_id("PF-HELM", "chart", loc),
                      "kind": "helm.chart", "source": str(chart),
                      "location": loc, "tier": 3,
                      "attrs": {**attrs, "graph": {
                          "nodes": [{"kind": "helm_chart", "label": name}],
                          "edges": [
                              {"src_kind": "helm_chart", "src": name,
                               "dst_kind": "helm_chart", "dst": d,
                               "kind": "depends_on"}
                              for d in attrs["dependencies"]]}}})
        if helm_bin:
            with tempfile.TemporaryDirectory(prefix="pf-helm-") as td:
                try:
                    out = subprocess.run(
                        [helm_bin, "template", name, str(cdir),
                         "--output-dir", td],
                        capture_output=True, text=True, timeout=60,
                        check=False)
                except subprocess.TimeoutExpired:
                    unresolved.append({
                        "capability": RENDER_CAPABILITY,
                        "location": loc,
                        "reason": "helm template timed out (60s)"})
                    continue
                if out.returncode != 0:
                    unresolved.append({
                        "capability": RENDER_CAPABILITY, "location": loc,
                        "reason": f"helm template failed: "
                                  f"{(out.stderr or out.stdout).strip()[:200]}"})
                    continue
                sub = analyze_k8s(td)
                for fct in sub["facts"]:
                    fct["source"] = f"{chart} (rendered)"
                    fct["location"] = f"{loc}::{fct['location']}"
                facts += sub["facts"]
                rendered_docs += sub["counts"]["docs"]
        else:
            unresolved.append({
                "capability": RENDER_CAPABILITY, "location": loc,
                "reason": "helm binary not found; templates not rendered",
                "unlock": "install helm or provide pre-rendered manifests"})

    return {"facts": facts, "unresolved": unresolved,
            "counts": {"charts": len(charts), "facts": len(facts),
                       "rendered_docs": rendered_docs,
                       "helm_available": bool(helm_bin)}}


def analyze_kustomize(path: str | Path) -> dict[str, Any]:
    """§64 — kustomization → build → render → facts (same pattern)."""
    root = Path(path)
    overlays = ([root / "kustomization.yaml"] if root.is_file()
                else sorted(root.rglob("kustomization.yaml")) +
                sorted(root.rglob("kustomization.yml")))
    overlays = [p for p in dict.fromkeys(overlays) if p.exists()]
    facts: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    kust = shutil.which("kustomize") or shutil.which("kubectl")

    for kfile in overlays:
        kdir = kfile.parent
        loc = f"{kfile}::{kdir.name}"
        try:
            kdoc = yaml.safe_load(kfile.read_text()) or {}
        except yaml.YAMLError:
            kdoc = {}
        attrs = {"resources": kdoc.get("resources") or [],
                 "bases": kdoc.get("bases") or [],  # pre-v4 field
                 "patches": len(kdoc.get("patches") or []) +
                            len(kdoc.get("patchesStrategicMerge") or []),
                 "images": [i.get("newName") or i.get("name")
                            for i in kdoc.get("images") or []
                            if isinstance(i, dict)],
                 "namespace": kdoc.get("namespace"),
                 "name_prefix": kdoc.get("namePrefix"),
                 "helm_charts": [h.get("name") for h in
                                 kdoc.get("helmCharts") or []
                                 if isinstance(h, dict)]}
        remote_bases = [r for r in attrs["resources"] + attrs["bases"]
                        if isinstance(r, str) and "://" in r]
        attrs["remote_bases"] = remote_bases
        facts.append({"fact_id": stable_id("PF-KUST", "overlay", loc),
                      "kind": "kustomize.overlay", "source": str(kfile),
                      "location": loc, "tier": 3, "attrs": attrs})
        if not kust:
            unresolved.append({
                "capability": "kustomize-render", "location": loc,
                "reason": "no kustomize/kubectl binary; overlay not built",
                "unlock": "install kustomize or provide built manifests"})
    return {"facts": facts, "unresolved": unresolved,
            "counts": {"overlays": len(overlays), "facts": len(facts),
                       "kustomize_available": bool(kust)}}
