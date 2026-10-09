"""§96–97 Kyverno + admission policy analysis — version-aware.

Legacy `Policy`/`ClusterPolicy` vs modern CEL-based types
(`ValidatingPolicy`, `MutatingPolicy`, `GeneratingPolicy`,
`ImageValidatingPolicy`, `PolicyException`). Whether a type is
deprecated depends on the Kyverno version — without a declared version
the finding is `version_unresolved`, never a guess.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from platformforge.models.base import stable_id

KYVERNO_KINDS = {"Policy", "ClusterPolicy", "ValidatingPolicy",
                 "MutatingPolicy", "GeneratingPolicy",
                 "ImageValidatingPolicy", "PolicyException",
                 "CleanupPolicy", "ValidatingAdmissionPolicy",
                 "ValidatingAdmissionPolicyBinding"}

# legacy kinds whose deprecation depends on declared engine version
LEGACY_KINDS = {"Policy", "ClusterPolicy"}
CEL_KINDS = {"ValidatingPolicy", "MutatingPolicy", "GeneratingPolicy",
             "ImageValidatingPolicy", "ValidatingAdmissionPolicy",
             "ValidatingAdmissionPolicyBinding"}

_GATEKEEPER_TMPL = {"ConstraintTemplate", "Constraint"}


def analyze_kyverno(path: str | Path,
                    kyverno_version: str | None = None) -> dict[str, Any]:
    root = Path(path)
    files = (sorted(root.rglob("*.yaml")) + sorted(root.rglob("*.yml"))) \
        if root.is_dir() else [root]
    facts: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    for f in files:
        try:
            docs = list(yaml.safe_load_all(f.read_text()))
        except (OSError, yaml.YAMLError):
            continue
        for doc in docs:
            if not isinstance(doc, dict):
                continue
            kind, api = doc.get("kind", ""), str(doc.get("apiVersion", ""))
            meta = doc.get("metadata") or {}
            name = meta.get("name", "?")
            loc = f"{f}::{name}"

            if "kyverno.io" in api or "policies.kyverno.io" in api \
                    or kind in KYVERNO_KINDS - _GATEKEEPER_TMPL:
                spec = doc.get("spec") or {}
                rules = spec.get("rules") or []
                mode = spec.get("validationFailureAction") or \
                    spec.get("failurePolicy")
                is_legacy = kind in LEGACY_KINDS
                attrs = {"policy_kind": kind, "api": api,
                         "rules": len(rules),
                         "failure_action": mode,
                         "background": spec.get("background"),
                         "legacy_type": is_legacy,
                         "cel_type": kind in CEL_KINDS,
                         "kyverno_version": kyverno_version}
                if is_legacy and kyverno_version is None:
                    unresolved.append({
                        "capability": "kyverno-version-check",
                        "location": loc,
                        "reason": "legacy kind without declared kyverno "
                                  "version — deprecation is version-bound",
                        "unlock": "pass kyverno_version to analyze_kyverno"})
                if is_legacy and kyverno_version:
                    try:
                        major = int(str(kyverno_version).lstrip("v")
                                    .split(".")[0])
                        attrs["legacy_deprecated"] = major >= 2 \
                            or (major == 1 and
                                int(str(kyverno_version)
                                    .split(".")[1]) >= 13)
                    except (ValueError, IndexError):
                        attrs["legacy_deprecated"] = None
                facts.append({
                    "fact_id": stable_id("PF-KYV", kind, loc),
                    "kind": "kyverno.policy", "source": str(f),
                    "location": loc, "tier": 3, "attrs": {
                        **attrs, "graph": {
                            "nodes": [{"kind": "admission_policy",
                                       "label": name}], "edges": []}}})
            elif kind in _GATEKEEPER_TMPL or \
                    "templates.gatekeeper.sh" in api or \
                    "constraints.gatekeeper.sh" in api:
                facts.append({
                    "fact_id": stable_id("PF-GK", kind, loc),
                    "kind": "gatekeeper.constraint", "source": str(f),
                    "location": loc, "tier": 3,
                    "attrs": {"gatekeeper_kind": kind, "api": api,
                              "rego": bool(doc.get("spec", {})
                                           .get("targets")),
                              "graph": {"nodes": [{"kind": "admission_policy",
                                                   "label": name}],
                                        "edges": []}}})
    return {"facts": facts, "unresolved": unresolved,
            "counts": {"facts": len(facts)}}
