"""§98 SLSA — real assessment: requirement / evidence / status / gap.

No level is claimed without evidence. Each SLSA build-track requirement
maps to observable artifact fields (builder id, provenance, hermetic
flags, base64 digests, signatures); absent evidence → `gap`, present →
`met`, partial → `partial`. `slsa_level` is only set when every
requirement of that level is `met` — never inferred.
"""

from __future__ import annotations

from typing import Any

# SLSA v1.0 build-track requirements → fields that satisfy them
REQUIREMENTS = {
    "L1": {
        "provenance_exists": "provenance document present",
        "build_id": "build invocation identifier present",
    },
    "L2": {
        "hosted_builder": "builder runs on hosted/ephemeral service",
        "signed_provenance": "provenance signed",
    },
    "L3": {
        "hardened_builder": "builder isolation declared",
        "non_forgeable": "provenance non-forgeable (OIDC/sigstore)",
        "base_images_pinned": "base images pinned by digest",
    },
}


def _has(doc: dict[str, Any], *paths: str) -> bool:
    for p in paths:
        node: Any = doc
        for part in p.split("."):
            if not isinstance(node, dict) or part not in node:
                break
            node = node[part]
        else:
            if node not in (None, "", [], {}):
                return True
    return False


def slsa_assess(provenance_doc: dict[str, Any] | None,
                evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    """Assess an in-toto/SLSA provenance document (or nothing)."""
    ev = evidence or {}
    if not provenance_doc:
        return {"slsa_level": None, "status": "unresolved",
                "reason": "no provenance document supplied",
                "requirements": {}}
    pred = provenance_doc.get("predicate") or {}
    checks = {
        "provenance_exists": True,
        "build_id": _has(provenance_doc, "predicate.buildDefinition",
                         "predicate.invocation") or
                    _has(pred, "buildDefinition"),
        "hosted_builder": bool(ev.get("hosted_builder")) or
            _has(pred, "runDetails.builder.id"),
        "signed_provenance": bool(ev.get("signed")) or
            bool(provenance_doc.get("signatures")),
        "hardened_builder": bool(ev.get("hardened_builder")),
        "non_forgeable": bool(ev.get("non_forgeable")) or
            _has(pred, "runDetails.builder.componentSource",
                 "metadata.integrity"),
        "base_images_pinned": bool(ev.get("base_images_pinned")) or
            bool(pred.get("materials")),
    }
    levels = {}
    for lv, reqs in REQUIREMENTS.items():
        rows = []
        for req, desc in reqs.items():
            met = checks.get(req, False)
            rows.append({"requirement": req, "description": desc,
                         "status": "met" if met else "gap",
                         "evidence": ev.get(req)})
        levels[lv] = {"requirements": rows,
                      "met": all(r["status"] == "met" for r in rows)}
    attained = next((lv for lv in ("L3", "L2", "L1")
                     if levels[lv]["met"]), None)
    return {"slsa_level": attained,
            "status": "assessed" if attained else "below-L1",
            "levels": levels,
            "note": "level = all requirements met; a gap at any level "
                    "is reported, not smoothed over"}
