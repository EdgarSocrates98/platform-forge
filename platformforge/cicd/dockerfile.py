"""Dockerfile analyzer — build-time surface as declared facts (T3).

Per Dockerfile: base images (+ pin style), USER, EXPOSE, package
installs, ADD-vs-COPY, healthcheck presence. Read-only.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from platformforge.models.base import stable_id

_RE_FROM = re.compile(r"^\s*FROM\s+([^\s]+)", re.MULTILINE | re.IGNORECASE)
_RE_USER = re.compile(r"^\s*USER\s+(\S+)", re.MULTILINE | re.IGNORECASE)
_RE_EXPOSE = re.compile(r"^\s*EXPOSE\s+(\S+)", re.MULTILINE | re.IGNORECASE)
_RE_ADD = re.compile(r"^\s*ADD\s+", re.MULTILINE | re.IGNORECASE)
_RE_HEALTH = re.compile(r"^\s*HEALTHCHECK\s", re.MULTILINE | re.IGNORECASE)
_RE_PKG = re.compile(
    r"(apt-get|apt|apk|yum|dnf|pip|npm)\s+install", re.IGNORECASE)


def _pin(ref: str) -> str:
    if "@sha256:" in ref:
        return "digest"
    if ":" in ref:
        return "tag"          # tags are mutable
    if ref.upper() == "SCRATCH" or ref.startswith("${"):
        return "variable"
    return "unpinned"


def analyze_dockerfile(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    files = [p] if p.is_file() else sorted(p.rglob("Dockerfile*"))
    facts: list[dict[str, Any]] = []
    for f in files:
        try:
            text = f.read_text()
        except (OSError, UnicodeDecodeError):
            continue
        bases = _RE_FROM.findall(text)
        users = _RE_USER.findall(text)
        last_user = users[-1] if users else ""
        facts.append({
            "fact_id": stable_id("dockerfile", str(f)),
            "kind": "cicd.dockerfile",
            "source": str(f),
            "location": str(f),
            "tier": 3,
            "attrs": {
                "base_images": bases,
                "unpinned_bases": [b for b in bases
                                   if _pin(b) in ("tag", "unpinned")],
                "runs_as_root": (last_user in ("", "root", "0")),
                "exposed_ports": _RE_EXPOSE.findall(text),
                "uses_add": bool(_RE_ADD.search(text)),
                "has_healthcheck": bool(_RE_HEALTH.search(text)),
                "package_managers": sorted(
                    {m.lower() for m in _RE_PKG.findall(text)}),
                "stage_count": len(bases),
            }})
    return {"facts": facts}
