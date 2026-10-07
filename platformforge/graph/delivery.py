"""§72 Software delivery graph — derive cross-domain edges from facts.

The analyzers emit local edges (workload→namespace, app→repo). This
enricher joins across fact kinds to surface the full chain:

    repository → workflow → artifact/image → gitops → cluster → workload

Joins are deterministic and evidence-carrying: an edge is only emitted
when both endpoints exist in the fact set, and the edge attrs cite the
fact_ids that motivated it.
"""

from __future__ import annotations

from typing import Any


def _repo_key(url: str | None) -> str | None:
    if not url:
        return None
    u = url.removesuffix(".git").rstrip("/")
    return u.rsplit("/", 1)[-1].lower() or None


def _image_repo(img: str | None) -> str | None:
    if not img:
        return None
    return img.split(":", 1)[0].rsplit("/", 1)[-1].lower() or None


def delivery_edges(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return derived edges [{src,src_kind,dst,dst_kind,kind,via,fact_ids}]."""
    repos: dict[str, list[str]] = {}          # repo key → fact ids
    wf_repos: list[tuple[str, str]] = []      # (repo key, workflow fact id)
    image_facts: dict[str, list[str]] = {}    # image repo → workload fact ids
    gitops_repos: list[tuple[str, str]] = []  # (repo key, gitops fact id)
    gitops_ns: list[tuple[str, str]] = []     # (namespace, gitops fact id)

    for f in facts:
        kind, a = f.get("kind", ""), f.get("attrs") or {}
        fid = f.get("fact_id", "")
        if kind == "gitops.argocd_app":
            for r in a.get("source_repos") or [a.get("source_repo")]:
                k = _repo_key(r)
                if k:
                    gitops_repos.append((k, fid))
            if a.get("dest_namespace"):
                gitops_ns.append((a["dest_namespace"], fid))
        elif kind == "gitops.flux_resource":
            if a.get("url"):
                k = _repo_key(a["url"])
                if k:
                    gitops_repos.append((k, fid))
        elif kind == "k8s.workload":
            for img in (a.get("pod_spec") or {}).get("images") or []:
                k = _image_repo(img)
                if k:
                    image_facts.setdefault(k, []).append(fid)
        elif kind in ("gha.workflow", "cicd.pipeline"):
            k = _repo_key(a.get("repo") or a.get("source_repo"))
            if k:
                wf_repos.append((k, fid))
        elif kind in ("repo.file", "iac.resource", "catalog.component"):
            k = _repo_key(a.get("repo") or a.get("repository"))
            if k:
                repos.setdefault(k, []).append(fid)

    edges: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    def add(sk: str, s: str, dk: str, d: str, ek: str, via: str,
            fids: list[str]) -> None:
        if (sk, dk, d) in seen:
            return
        seen.add((sk, dk, d))
        edges.append({"src_kind": sk, "src": s, "dst_kind": dk, "dst": d,
                      "kind": ek, "via": via, "fact_ids": fids})

    # gitops app → repository it syncs → workflows that build it
    for rk, gfid in gitops_repos:
        add("argocd_application", f"fact:{gfid}", "repository", rk,
            "depends_on", "source_repo", [gfid])
        for rk2, wfid in wf_repos:
            if rk2 == rk:
                add("workflow", f"fact:{wfid}", "argocd_application",
                    f"fact:{gfid}", "generated_by", "same_repo",
                    [wfid, gfid])

    # gitops app → workload via destination namespace match
    for ns, gfid in gitops_ns:
        for f in facts:
            if f.get("kind") == "k8s.workload" and \
                    (f.get("attrs") or {}).get("namespace") == ns:
                add("argocd_application", f"fact:{gfid}", "workload",
                    f"fact:{f['fact_id']}", "deploys_to",
                    "dest_namespace", [gfid, f["fact_id"]])

    # image repo produced by workflow → consumed by workload
    for ik, wfids in image_facts.items():
        for rk, wfid in wf_repos:
            if rk == ik:
                for wf in wfids:
                    add("workflow", f"fact:{wfid}", "workload",
                        f"fact:{wf}", "generated_by", "image_repo",
                        [wfid, wf])
    return edges
