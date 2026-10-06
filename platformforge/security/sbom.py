"""SBOM ingest — CycloneDX and SPDX JSON → component facts. Optional offline
CVE match against a caller-provided vuln list (never a network call)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from platformforge.models.base import stable_id


def analyze_sbom(path: str | Path,
                 vuln_db: dict[str, list[str]] | None = None) -> dict[str, Any]:
    """vuln_db: {"name@version": ["CVE-..."]} supplied by caller — offline."""
    doc = json.loads(Path(path).read_text())
    comps: list[dict[str, Any]] = []
    fmt = "unknown"
    if doc.get("bomFormat") == "CycloneDX":
        fmt = "cyclonedx"
        for c in doc.get("components") or []:
            comps.append({"name": c.get("name"), "version": c.get("version"),
                          "type": c.get("type"),
                          "licenses": [l.get("license", {}).get("id")
                                       or l.get("license", {}).get("name")
                                       for l in c.get("licenses") or []],
                          "purl": c.get("purl"),
                          "supplier": (c.get("supplier") or {}).get("name")})
    elif doc.get("spdxVersion"):
        fmt = "spdx"
        for p in doc.get("packages") or []:
            comps.append({"name": p.get("name"), "version": p.get("versionInfo"),
                          "type": p.get("primaryPackagePurpose"),
                          "licenses": [p.get("licenseConcluded")]
                          if p.get("licenseConcluded") else [],
                          "supplier": p.get("supplier")})
    vulns: dict[str, list[str]] = {}
    for c in comps:
        key = f"{c['name']}@{c['version']}"
        if vuln_db and key in vuln_db:
            vulns[key] = vuln_db[key]
    copyleft = [c["name"] for c in comps
                if any(l and ("GPL" in l or "AGPL" in l or "SSPL" in l)
                       for l in c.get("licenses", []))]
    no_license = [c["name"] for c in comps if not c.get("licenses")]
    facts = [{"fact_id": stable_id("PF-SEC", "sbom", str(path)),
              "kind": "security.sbom", "source": str(path), "tier": 3,
              "location": str(path),
              "attrs": {"format": fmt, "component_count": len(comps),
                        "components": comps[:500],  # bounded
                        "truncated": len(comps) > 500,
                        "vulnerabilities": vulns,
                        "vuln_count": sum(len(v) for v in vulns.values()),
                        "copyleft_components": copyleft,
                        "unlicensed_components": no_license,
                        "graph": {
                            "nodes": [{"kind": "sbom", "label": str(path)}],
                            "edges": []}}}]
    return {"facts": facts, "counts": {"components": len(comps)}}
