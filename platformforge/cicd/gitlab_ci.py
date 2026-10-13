"""GitLab CI analyzer — pipeline surface as declared facts (T3).

Per pipeline: stages, jobs, images, services, `only`/`rules` triggers,
cache usage. Read-only — never executes the pipeline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from platformforge.models.base import stable_id


def analyze_gitlab_ci(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    f = p if p.is_file() else p / ".gitlab-ci.yml"
    if not f.exists():
        return {"facts": [], "error": f"no .gitlab-ci.yml at {p}"}
    try:
        doc = yaml.safe_load(f.read_text()) or {}
    except yaml.YAMLError as e:
        return {"facts": [], "error": f"yaml: {e}"}
    if not isinstance(doc, dict):
        return {"facts": [], "error": "not a mapping"}
    stages = doc.get("stages") or []
    jobs = {k: v for k, v in doc.items()
            if isinstance(v, dict) and isinstance(v.get("script"), (list, str))}
    images = sorted({str(j.get("image")) for j in jobs.values()
                     if j.get("image")})
    default_image = ""
    if isinstance(doc.get("default"), dict):
        default_image = str(doc["default"].get("image") or "")
    unpinned = [i for i in images + ([default_image] if default_image else [])
                if ":" not in i or i.endswith(":latest")]
    facts = [{
        "fact_id": stable_id("PF-GITLABCI", str(f)),
        "kind": "cicd.gitlab_pipeline",
        "source": str(f),
        "location": str(f),
        "tier": 3,
        "attrs": {
            "stages": list(stages),
            "jobs": sorted(jobs),
            "job_count": len(jobs),
            "images": images,
            "default_image": default_image,
            "unpinned_images": sorted(set(unpinned)),
            "uses_cache": any("cache" in j for j in jobs.values())
            or "cache" in doc,
            "has_rules": any("rules" in j or "only" in j or "except" in j
                             for j in jobs.values()),
        }}]
    return {"facts": facts}
