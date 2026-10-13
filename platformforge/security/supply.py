"""Supply chain — artifact digest pinning, SLSA/in-toto attestation shape,
unsigned-image detection. Offline: verifies declared metadata, not sigs."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from platformforge.models.base import stable_id

_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def analyze_supply(path: str | Path) -> dict[str, Any]:
    """Input: JSON doc {artifacts: [{name, image, digest, slsa_provenance?,
    signed?}], ...} or a single SLSA/in-toto attestation doc."""
    doc = json.loads(Path(path).read_text())
    facts: list[dict[str, Any]] = []

    # in-toto / SLSA attestation document
    if doc.get("_type") == "https://in-toto.io/Statement/v1" \
            or "predicateType" in doc or "subject" in doc:
        subj = doc.get("subject") or []
        ptype = doc.get("predicateType", "")
        facts.append({"fact_id": stable_id("PF-SEC", "attestation", str(path)),
                      "kind": "security.attestation", "source": str(path),
                      "location": str(path), "tier": 2,
                      "attrs": {
                          "predicate_type": ptype,
                          "is_slsa": "slsa" in ptype,
                          "subjects": len(subj),
                          "subject_digests_valid": all(
                              _DIGEST_RE.match(
                                  (s.get("digest") or {}).get("sha256", ""))
                              for s in subj) if subj else False,
                          "materials": len(
                              (doc.get("predicate") or {})
                              .get("materials") or []),
                          "note": "shape verified; signature NOT verified "
                                  "offline"}})
        return {"facts": facts, "counts": {"facts": 1}}

    # artifact inventory doc
    for a in doc.get("artifacts") or []:
        img = a.get("image") or a.get("name") or "?"
        digest = a.get("digest") or ""
        pinned = bool(_DIGEST_RE.match(digest)) or "@sha256:" in str(img)
        facts.append({
            "fact_id": stable_id("PF-SEC", "artifact", str(path), img),
            "kind": "security.artifact", "source": str(path),
            "location": img, "tier": 3,
            "attrs": {"image": img, "digest_pinned": pinned,
                      "signed": bool(a.get("signed")),
                      "slsa_provenance": bool(a.get("slsa_provenance")),
                      "sbom_ref": a.get("sbom"),
                      "graph": {
                          "nodes": [{"kind": "container_image",
                                     "label": img}],
                          "edges": []}}})
    return {"facts": facts, "counts": {"facts": len(facts)}}
