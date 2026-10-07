"""Crossplane — explicit object classifier (cycle 2.1 §51–59).

No naive wildcard: an apiGroup ending in ``upbound.io``/``crossplane.io`` is a
*signal*, not a verdict. Managed resources additionally require structural
evidence (``spec.forProvider``, ``status.atProvider``, ``providerConfigRef``,
management/deletion policy fields). Objects outside known families are never
classified — ``foo.example.com/v1`` stays invisible, by design (§58).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from platformforge.models.base import stable_id

# Core Crossplane API families → kind → fact kind.
_CORE_KINDS: dict[str, dict[str, str]] = {
    "apiextensions.crossplane.io": {
        "CompositeResourceDefinition": "platform.xrd",
        "Composition": "platform.composition",
        "CompositionRevision": "platform.composition_revision",
        "EnvironmentConfig": "platform.crossplane_envconfig",
    },
    "pkg.crossplane.io": {
        "Provider": "platform.crossplane_provider",
        "ProviderRevision": "platform.crossplane_provider_revision",
        "Configuration": "platform.crossplane_configuration",
        "ConfigurationRevision": "platform.crossplane_configuration_revision",
        "Function": "platform.crossplane_function",
        "DeploymentRuntimeConfig": "platform.crossplane_runtime_config",
        "ImageConfig": "platform.crossplane_image_config",
        "Lock": "platform.crossplane_lock",
    },
    "ops.crossplane.io": {
        "Operation": "platform.crossplane_operation",
        "CronOperation": "platform.crossplane_operation",
    },
    "secrets.crossplane.io": {
        "StoreConfig": "platform.crossplane_storeconfig",
    },
    "apiextensions.crossplane.io/v2": {},
}

# Provider-shaped group suffixes. Membership here is necessary but not
# sufficient for ManagedResource — structural evidence is still required.
_PROVIDER_GROUP_SUFFIXES = (".upbound.io", "upbound.io", ".crossplane.io")

# Strong MR shape — one is sufficient. Weak fields (writeConnectionSecretToRef
# etc.) also appear on claims and Upbound Spaces objects, so they never
# classify alone (§53/§58).
_MR_STRONG_FIELDS = ("forProvider", "providerConfigRef", "managementPolicies")
_MR_WEAK_FIELDS = ("writeConnectionSecretToRef", "publishConnectionDetailsTo")


def _group(api_version: str) -> str:
    return api_version.rsplit("/", 1)[0] if "/" in api_version else ""


def _provider_family(group: str) -> str:
    """aws.s3.upbound.io → aws; database.aws.crossplane.io → aws (legacy)."""
    for seg in group.split("."):
        if seg in ("aws", "azure", "azuread", "gcp", "google", "alibaba",
                   "digitalocean", "ibm", "oci", "openstack", "vault",
                   "kubernetes", "helm", "terraform", "netlify", "github",
                   "gitlab", "datadog", "grafana", "mongodb", "kafka"):
            return seg
    return "unknown"


def _mr_evidence(spec: dict[str, Any], status: dict[str, Any]) -> list[str]:
    """Strong evidence only — weak fields never unlock classification."""
    ev = [f"spec.{k}" for k in _MR_STRONG_FIELDS if k in spec]
    if isinstance(status.get("atProvider"), dict):
        ev.append("status.atProvider")
    return ev


def _version_signals(kind: str, api: str, spec: dict[str, Any]) -> list[str]:
    """Per-object v1/v2 cues — inferred, never a global claim (§55)."""
    sig: list[str] = []
    ver = api.rsplit("/", 1)[-1]
    if kind == "CompositeResourceDefinition":
        scope = str(spec.get("scope", "")).lower()
        if scope == "namespaced":
            sig.append("v2:namespaced-xr")
        elif scope == "cluster":
            sig.append("v1:cluster-xr")
        if spec.get("claimNames"):
            sig.append("v1:claim-names")
        if spec.get("connectionSecretKeys"):
            sig.append("v1:connection-secret-keys")
    elif kind == "Composition":
        mode = str(spec.get("mode", "")).lower()
        if mode == "pipeline" or spec.get("pipeline"):
            sig.append("pipeline-mode")
        elif spec.get("resources"):
            sig.append("resources-mode")
    elif ver.startswith("v2"):
        sig.append(f"api:{ver}")
    return sig


def _provider_group(group: str) -> bool:
    return any(group == s or group.endswith(s) for s in _PROVIDER_GROUP_SUFFIXES)


def classify_object(doc: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    """Classify one manifest → (fact_kind, attrs) or None.

    Returns None for anything that is not structurally a Crossplane object.
    """
    kind = doc.get("kind")
    if not kind:
        return None
    api = str(doc.get("apiVersion", ""))
    group = _group(api)
    meta = doc.get("metadata") or {}
    spec = doc.get("spec") or {}
    status = doc.get("status") or {}
    name = meta.get("name", "?")

    # 1. Core families — exact (group, kind) membership.
    if group in _CORE_KINDS and kind in _CORE_KINDS[group]:
        fk = _CORE_KINDS[group][kind]
        attrs: dict[str, Any] = {"api": api, "name": name,
                                 "version_signals":
                                     _version_signals(kind, api, spec)}
        if fk == "platform.xrd":
            attrs.update({
                "xrd": name, "group": spec.get("group"),
                "xr_kind": next((v.get("kind") for v in
                                 spec.get("versions") or [] if v.get("kind")),
                                (spec.get("names") or {}).get("kind")),
                "scope": spec.get("scope", "Cluster"),
                "kind_claim": (spec.get("claimNames") or {}).get("kind"),
                "versions": [v.get("name")
                             for v in spec.get("versions") or []],
                "connection_secret_keys":
                    spec.get("connectionSecretKeys") or [],
            })
        elif fk == "platform.composition":
            attrs.update({
                "composition": name,
                "composite_type": (spec.get("compositeTypeRef") or {})
                                  .get("kind"),
                "composite_type_api": (spec.get("compositeTypeRef") or {})
                                      .get("apiVersion"),
                "resources": len(spec.get("resources") or []),
                "pipeline_mode": bool(spec.get("pipeline"))
                    or spec.get("mode") == "Pipeline",
                "functions": [(p.get("functionRef") or {}).get("name")
                              for p in spec.get("pipeline") or []
                              if p.get("functionRef")],
            })
        elif fk == "platform.composition_revision":
            attrs.update({"composition_revision": name,
                          "revision": meta.get("labels", {}).get(
                              "crossplane.io/composition-revision")})
        elif fk in ("platform.crossplane_provider",
                    "platform.crossplane_provider_revision",
                    "platform.crossplane_function",
                    "platform.crossplane_configuration"):
            attrs.update({"package": spec.get("package"),
                          "revision_activation_policy":
                              spec.get("revisionActivationPolicy")})
        elif fk == "platform.crossplane_operation":
            attrs.update({"operation": name,
                          "mode": spec.get("mode"),
                          "schedule": (spec.get("schedule") or {})
                                     .get("cron")})
        return fk, attrs

    # 2. ProviderConfig lives in provider family groups (v2 moved it out of
    #    pkg.crossplane.io).
    if kind in ("ProviderConfig", "ClusterProviderConfig") and (
            _provider_group(group) or "provider" in group):
        return "platform.provider_config", {
            "api": api, "name": name, "provider_family":
                _provider_family(group),
            "credentials_source": ((spec.get("credentials") or {})
                                   .get("source"))}

    # 3. ManagedResource — provider group suffix AND structural evidence.
    if _provider_group(group):
        ev = _mr_evidence(spec, status)
        if ev:
            return "platform.managed_resource", {
                "managed_kind": kind, "name": name, "api": api,
                "provider_group": group,
                "provider_family": _provider_family(group),
                "mr_evidence": ev,
                "for_provider_keys": sorted(
                    (spec.get("forProvider") or {}).keys())[:20],
                "deletion_policy": spec.get("deletionPolicy", "Delete"),
                "management_policies": spec.get("managementPolicies") or [],
                "provider_config_ref": (spec.get("providerConfigRef") or {})
                                       .get("name"),
                "version_signals": _version_signals(kind, api, spec)}
        return None  # §53 — suffix alone is not classification

    # 4. XR / Claim candidates — referenced by an XRD in the same tree, or
    #    carry composition plumbing. Handled by the caller (needs XRD table).
    return None


def _xr_candidate(doc: dict[str, Any],
                  xrd_kinds: dict[tuple[str, str], dict[str, Any]]
                  ) -> tuple[str, dict[str, Any]] | None:
    """XR/claim classification — needs the XRD table or composition refs."""
    kind = doc.get("kind")
    api = str(doc.get("apiVersion", ""))
    group = _group(api)
    spec = doc.get("spec") or {}
    meta = doc.get("metadata") or {}
    name = meta.get("name", "?")
    if not kind or group in _CORE_KINDS or _provider_group(group):
        return None
    key = (group, kind)
    comp_ref = (spec.get("compositionRef") or {}).get("name")
    res_refs = spec.get("resourceRefs") or []
    if key in xrd_kinds:
        xr = xrd_kinds[key]
        role = "xr_claim" if xr.get("kind_claim") == kind else "xr"
        return f"platform.{role}", {
            "xr_kind": kind, "api": api, "name": name,
            "xrd": xr["xrd"], "composition_ref": comp_ref,
            "classification": "declared-xrd",
            "version_signals": _version_signals(kind, api, spec)}
    if comp_ref or res_refs:
        return "platform.xr", {
            "xr_kind": kind, "api": api, "name": name,
            "composition_ref": comp_ref,
            "classification": "inferred-composition-ref",
            "version_signals": _version_signals(kind, api, spec)}
    return None


def analyze_crossplane(path: str | Path) -> dict[str, Any]:
    root = Path(path)
    files = (sorted(root.rglob("*.yaml")) + sorted(root.rglob("*.yml"))) \
        if root.is_dir() else [root]
    docs: list[tuple[Path, dict[str, Any]]] = []
    for f in files:
        try:
            for doc in yaml.safe_load_all(f.read_text()):
                if isinstance(doc, dict) and doc.get("kind"):
                    docs.append((f, doc))
        except yaml.YAMLError:
            continue

    # Pass 1 — classify and collect the XRD table for pass 2.
    classified: list[tuple[Path, dict[str, Any], str, dict[str, Any]]] = []
    xrd_kinds: dict[tuple[str, str], dict[str, Any]] = {}
    deferred: list[tuple[Path, dict[str, Any]]] = []
    for f, doc in docs:
        out = classify_object(doc)
        if out is None:
            deferred.append((f, doc))
            continue
        fk, attrs = out
        classified.append((f, doc, fk, attrs))
        if fk == "platform.xrd" and attrs.get("group"):
            if attrs.get("xr_kind"):
                xrd_kinds[(attrs["group"], attrs["xr_kind"])] = attrs
            if attrs.get("kind_claim"):
                xrd_kinds[(attrs["group"], attrs["kind_claim"])] = attrs

    # Pass 2 — XR/claim candidates against the XRD table.
    for f, doc in deferred:
        out = _xr_candidate(doc, xrd_kinds)
        if out:
            fk, attrs = out
            classified.append((f, doc, fk, attrs))

    facts: list[dict[str, Any]] = []
    for f, doc, fk, attrs in classified:
        meta = doc.get("metadata") or {}
        name = meta.get("name", "?")
        loc = f"{f}::{name}"
        node_kind = {
            "platform.xrd": "crossplane_xrd",
            "platform.xr": "crossplane_xr",
            "platform.xr_claim": "crossplane_xr",
            "platform.composition": "crossplane_composition",
            "platform.managed_resource": "crossplane_managed_resource",
            "platform.crossplane_provider": "crossplane_provider",
            "platform.provider_config": "crossplane_provider",
        }.get(fk, "crossplane_xr")
        edges: list[dict[str, Any]] = []
        # XR → Composition → XRD and MR → ProviderConfig edges (§59).
        if fk in ("platform.xr", "platform.xr_claim") and attrs.get(
                "composition_ref"):
            edges.append({"src_kind": "crossplane_xr", "src": name,
                          "dst_kind": "crossplane_composition",
                          "dst": attrs["composition_ref"],
                          "kind": "provisioned_by",
                          "provenance": "declared"})
        elif fk == "platform.composition" and attrs.get("composite_type"):
            # Resolve compositeTypeRef (group+kind) to the XRD's metadata
            # name when the XRD is in the same tree; else keep the kind.
            ref_group = _group(attrs.get("composite_type_api") or "")
            xrd = xrd_kinds.get((ref_group, attrs["composite_type"]), {})
            xrd_label = xrd.get("xrd") or attrs["composite_type"]
            edges.append({"src_kind": "crossplane_composition",
                          "src": name,
                          "dst_kind": "crossplane_xrd",
                          "dst": xrd_label,
                          "kind": "provisioned_by",
                          "provenance": "declared" if xrd else "inferred",
                          "confidence": 1.0 if xrd else 0.5})
        elif fk == "platform.managed_resource" and attrs.get(
                "provider_config_ref"):
            edges.append({"src_kind": "crossplane_managed_resource",
                          "src": name,
                          "dst_kind": "crossplane_provider",
                          "dst": attrs["provider_config_ref"],
                          "kind": "provisioned_by",
                          "provenance": "declared"})
        attrs["graph"] = {"nodes": [{"kind": node_kind, "label": name}],
                          "edges": edges}
        facts.append({"fact_id": stable_id("PF-XR", fk, loc),
                      "kind": fk, "source": str(f), "location": loc,
                      "tier": 3, "attrs": attrs})
    return {"facts": facts, "counts": {"facts": len(facts)}}
