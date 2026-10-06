"""GitHub Actions workflow analyzer — CI supply-chain surface as facts.

Per workflow: triggers, permissions, job steps, third-party actions with
pinning style (sha/tag/branch), secrets usage, self-hosted runners.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from platformforge.models.base import stable_id

_DANGEROUS_TRIGGERS = {"pull_request_target", "workflow_run"}
_WRITE_PERMS = {"contents": "write", "id-token": "write",
                "packages": "write", "actions": "write",
                "security-events": "write"}


def _action_ref(uses: str) -> dict[str, Any]:
    """`org/repo@ref` → {name, ref, pinned: sha|tag|branch|none}."""
    if not uses or uses.startswith("./") or uses.startswith("docker://"):
        return {"name": uses, "ref": None, "pin": "local"}
    name, _, ref = uses.partition("@")
    if not ref:
        pin = "unpinned"
    elif re.fullmatch(r"[0-9a-f]{40}", ref):
        pin = "sha"
    elif re.fullmatch(r"v?\d+(\.\d+)*", ref):
        pin = "tag"  # tags are mutable
    else:
        pin = "branch"
    return {"name": name, "ref": ref, "pin": pin,
            "third_party": not name.startswith(("actions/", "github/"))}


def analyze_gha(path: str | Path) -> dict[str, Any]:
    root = Path(path)
    wf_dir = root / ".github" / "workflows" if root.is_dir() else None
    files = ([*wf_dir.glob("*.yml"), *wf_dir.glob("*.yaml")]
             if wf_dir and wf_dir.is_dir()
             else ([root] if root.is_file() else []))
    facts: list[dict[str, Any]] = []
    for f in sorted(set(files)):
        try:
            doc = yaml.safe_load(f.read_text()) or {}
        except yaml.YAMLError:
            continue
        if not isinstance(doc, dict) or "jobs" not in doc:
            continue
        name = doc.get("name") or f.stem
        triggers = doc.get(True) or doc.get("on") or {}  # YAML 1.1 `on:`→True
        if isinstance(triggers, str):
            triggers = {triggers: {}}
        perms = doc.get("permissions") or {}
        if isinstance(perms, str):
            perms = {"all": perms}
        jobs = doc.get("jobs") or {}
        uses_list, secrets_used = [], []
        unpinned, dangerous, self_hosted = [], [], []
        script_injection = []
        for jname, job in jobs.items():
            job = job or {}
            if job.get("runs-on") and "self-hosted" in \
                    (job["runs-on"] if isinstance(job["runs-on"], list)
                     else [job["runs-on"]]):
                self_hosted.append(jname)
            jperms = job.get("permissions") or {}
            if isinstance(jperms, str):
                jperms = {"all": jperms}
            for k, v in jperms.items():
                if v in ("write", "write-all"):
                    perms[k] = v
            for step in job.get("steps") or []:
                if "uses" in step:
                    ref = _action_ref(step["uses"])
                    uses_list.append(ref)
                    if ref["pin"] in ("unpinned", "branch", "tag") \
                            and ref["third_party"]:
                        unpinned.append(f"{jname}:{ref['name']}@{ref['ref']}")
                run = step.get("run") or ""
                if "${{" in run and any(
                        t in run for t in
                        ("github.event.issue", "github.event.comment",
                         "github.event.pull_request.title",
                         "github.event.pull_request.body",
                         "github.head_ref")):
                    script_injection.append(jname)
                env = step.get("env") or {}
                for v in env.values():
                    if isinstance(v, str) and "secrets." in v:
                        secrets_used.append(v)
        for t in triggers:
            if t in _DANGEROUS_TRIGGERS:
                dangerous.append(t)
        write_perms = [k for k, v in perms.items()
                       if v in ("write", "write-all") or v == "write-all"
                       or perms.get("all") in ("write", "write-all")]
        if isinstance(perms, dict) and perms.get("all") in ("write", "write-all"):
            write_perms = ["*"]
        attrs = {
            "workflow": name, "triggers": sorted(triggers),
            "dangerous_triggers": dangerous,
            "permissions": perms, "write_perms": write_perms,
            "jobs": sorted(jobs), "job_count": len(jobs),
            "actions": uses_list,
            "unpinned_third_party": unpinned,
            "self_hosted_jobs": self_hosted,
            "script_injection_risk": script_injection,
            "secrets_referenced": sorted(set(secrets_used)),
            "graph": {
                "nodes": [{"kind": "workflow",
                           "label": f"{f.parent.parent.parent.name}/{f.stem}"}],
                "edges": []},
        }
        facts.append({"fact_id": stable_id("PF-CICD", "gha", str(f)),
                      "kind": "cicd.github_workflow", "source": str(f),
                      "location": str(f), "tier": 3, "attrs": attrs})
    return {"facts": facts, "counts": {"workflows": len(facts)}}
