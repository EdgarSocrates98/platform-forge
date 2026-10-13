"""§99 Sigstore/Cosign — offline shape + attestation parsing.

The core parses signature bundle/attestation JSON structure (bundle
media types, DSSE envelopes, rekor/log entry presence) but never
verifies: `signed=true` in a document is *claimed*, not *verified*.
Actual verification is an optional host-side adapter boundary.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from platformforge.models.base import stable_id

SIG_BUNDLE_HINTS = ("verificationMaterial", "dsseEnvelope",
                    "rekorBundle", "signature", "signatures")


def analyze_cosign(path: str | Path) -> dict[str, Any]:
    root = Path(path)
    files = sorted(root.rglob("*.json")) if root.is_dir() else [root]
    facts: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    for f in files:
        try:
            doc = json.loads(f.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(doc, dict):
            continue
        has_bundle = any(k in doc for k in SIG_BUNDLE_HINTS)
        is_attest = doc.get("_type") or doc.get("predicateType")
        if not (has_bundle or is_attest):
            continue
        sigs = doc.get("signatures") or []
        claimed = bool(sigs) or "signature" in doc
        subj = doc.get("subject")
        subj_name = subj[0].get("name", "?") \
            if isinstance(subj, list) and subj else f.name
        loc = f"{f}::{subj_name}"
        facts.append({
            "fact_id": stable_id("PF-COSIGN", "sig", loc),
            "kind": "supply.signature", "source": str(f),
            "location": loc, "tier": 3,
            "attrs": {
                "claimed_signed": claimed,
                "verified": False,   # NEVER true offline
                "signature_count": len(sigs),
                "has_rekor_entry": "rekorBundle" in doc or
                                   "verificationMaterial" in doc,
                "dsse": "dsseEnvelope" in doc or "_type" in doc,
                "attestation": bool(is_attest),
                "note": "parsed shape only — signature is claimed, not "
                        "verified; verification is a host adapter"}})
        if claimed:
            unresolved.append({
                "capability": "cosign-verify",
                "location": loc,
                "reason": "signature present but verification requires "
                          "key lookup + rekor transparency check — "
                          "host-side boundary",
                "unlock": "run the cosign verify adapter with the "
                          "public key / fulcio bundle"})
    return {"facts": facts, "unresolved": unresolved,
            "counts": {"facts": len(facts)}}
