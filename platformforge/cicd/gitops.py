"""GitOps analyzers — ArgoCD Application/ApplicationSet, Flux Kustomization/
HelmRelease/GitRepository. Facts declare sync policy, sources, targets;
edges wire app → repo → cluster/namespace.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from platformforge.models.base import stable_id

ARGO_KINDS = {"Application", "ApplicationSet", "AppProject"}
FLUX_KINDS = {"GitRepository", "HelmRepository", "OCIRepository",
              "Kustomization", "HelmRelease", "HelmChart"}


def _docs(path: Path):
    files = (sorted(path.rglob("*.yaml")) + sorted(path.rglob("*.yml"))) \
        if path.is_dir() else [path]
    for f in files:
        try:
            for i, doc in enumerate(yaml.safe_load_all(f.read_text())):
                if isinstance(doc, dict) and doc.get("kind") \
                        and doc.get("apiVersion"):
                    yield f, doc
        except yaml.YAMLError:
            continue


def analyze_gitops(path: str | Path) -> dict[str, Any]:
    facts: list[dict[str, Any]] = []
    for f, doc in _docs(Path(path)):
        kind, meta = doc["kind"], doc.get("metadata") or {}
        spec = doc.get("spec") or {}
        name, ns = meta.get("name", "?"), meta.get("namespace", "default")
        loc = f"{f}::{ns}/{name}"
        api = doc.get("apiVersion", "")

        if kind in ARGO_KINDS and "argoproj.io" in api:
            sync = spec.get("syncPolicy") or {}
            # §69 — multi-source applications carry `sources[]`, not `source`
            sources = spec.get("sources") or ([spec["source"]]
                                              if spec.get("source") else [])
            src = sources[0] if sources else {}
            dest = spec.get("destination") or {}
            # ArgoCD: presence of `automated` (even `{}`/null) enables sync
            automated = "automated" in sync
            ann = meta.get("annotations") or {}
            attrs = {
                "name": name, "namespace": ns, "tool": "argocd",
                "automated_sync": automated,
                "prune": bool((sync.get("automated") or {}).get("prune")),
                "self_heal": bool((sync.get("automated") or {}).get("selfHeal")),
                "source_repo": src.get("repoURL"),
                "source_path": src.get("path"),
                "source_revision": src.get("targetRevision"),
                "source_count": len(sources),
                "source_repos": sorted({s.get("repoURL") for s in sources
                                        if s.get("repoURL")}),
                "dest_server": dest.get("server"),
                "dest_namespace": dest.get("namespace"),
                "project": spec.get("project"),
                # §69 sync waves + hooks (declared, T3)
                "sync_wave": ann.get("argocd.argoproj.io/sync-wave"),
                "has_hooks": "argocd.argoproj.io/hook" in ann,
                "app_project_scope": bool(spec.get("project")),
                "graph": {
                    "nodes": [{"kind": "argocd_application",
                               "label": f"{ns}/{name}",
                               "attrs": {"project": spec.get("project")}}],
                    "edges": []},
            }
            # §69 — kind-specific depth: ApplicationSet generators +
            # AppProject source/destination restrictions
            if kind == "ApplicationSet":
                gens = spec.get("generators") or []
                attrs["generators"] = [next(iter(g)) for g in gens
                                       if isinstance(g, dict) and g]
            elif kind == "AppProject":
                attrs["source_restrictions"] = len(spec.get("sourceRepos") or [])
                attrs["dest_restrictions"] = len(spec.get("destinations") or [])
                attrs["cluster_resource_whitelist"] = len(
                    spec.get("clusterResourceWhitelist") or [])
                attrs["roles"] = len(spec.get("roles") or [])
            edges = attrs["graph"]["edges"]
            if src.get("repoURL"):
                edges.append({"src_kind": "argocd_application",
                              "src": f"{ns}/{name}",
                              "dst_kind": "repository",
                              "dst": src["repoURL"].rsplit("/", 1)[-1]
                                     .removesuffix(".git"),
                              "kind": "depends_on"})
            if dest.get("namespace"):
                edges.append({"src_kind": "argocd_application",
                              "src": f"{ns}/{name}",
                              "dst_kind": "namespace",
                              "dst": dest["namespace"],
                              "kind": "deploys_to"})
            facts.append({"fact_id": stable_id("PF-GITOPS", "argocd", loc),
                          "kind": "gitops.argocd_app", "source": str(f),
                          "location": loc, "tier": 3, "attrs": attrs})
        elif kind in FLUX_KINDS and "toolkit.fluxcd.io" in api:
            src = spec.get("sourceRef") or {}
            interval = spec.get("interval")
            attrs = {
                "name": name, "namespace": ns, "tool": "fluxcd",
                "flux_kind": kind, "interval": interval,
                "prune": spec.get("prune"),
                "source_ref": f"{src.get('kind')}/{src.get('name')}"
                    if src else None,
                "url": spec.get("url"),
                "suspend": doc.get("spec", {}).get("suspend", False),
                "graph": {
                    "nodes": [{"kind": "fluxcd_resource",
                               "label": f"{ns}/{name}",
                               "attrs": {"flux_kind": kind}}],
                    "edges": []},
            }
            if src.get("name"):
                attrs["graph"]["edges"].append(
                    {"src_kind": "fluxcd_resource", "src": f"{ns}/{name}",
                     "dst_kind": "fluxcd_resource",
                     "dst": f"{ns}/{src['name']}", "kind": "depends_on"})
            facts.append({"fact_id": stable_id("PF-GITOPS", "flux", loc),
                          "kind": "gitops.flux_resource", "source": str(f),
                          "location": loc, "tier": 3, "attrs": attrs})
    return {"facts": facts, "counts": {"facts": len(facts)}}
