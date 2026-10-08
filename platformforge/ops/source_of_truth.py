"""Cycle 4 — SourceOfTruthResolver (§12–17, ADR-0022).

Before any remediation: *where should this resource actually be
changed?* Resolution is evidence-driven, precedence by provenance —
never blind. Unprovable ownership → `PF-OPS-SOURCE-UNKNOWN` + human
review. Never guess.

Signals come from facts/observations/graph nodes: an ArgoCD tracking
annotation on a k8s object, a `terraform_resource` fact, a Crossplane
managed resource, a Helm release secret. Each resolved answer carries
the evidence that produced it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from platformforge.ops.models import SourceOfTruth

# Signals we understand. Each maps evidence → SoT resolution.
ARGOCD_TRACKING = "argocd.argoproj.io/tracking-id"
ARGOCD_INSTANCE = "argocd.argoproj.io/instance"
FLUXCD_LABELS = ("kustomize.toolkit.fluxcd.io/name",
                 "helm.toolkit.fluxcd.io/name")
HELM_LABELS = ("app.kubernetes.io/managed-by",)
CROSSPLANE_CLAIM = "crossplane.io/claim-name"
TF_ADDRESS_ATTRS = ("tf_address", "terraform_address", "module_address")


@dataclass
class Resolution:
    resource_id: str = ""
    source: SourceOfTruth = field(default_factory=SourceOfTruth)
    preferred_path: str = ""        # git|terraform|gitops|direct — policy hint
    unresolved: dict[str, Any] | None = None
    conflicts: list[str] = field(default_factory=list)

    @property
    def resolved(self) -> bool:
        return self.unresolved is None and self.source.resolved

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"resource_id": self.resource_id,
                             "resolved": self.resolved,
                             "source_of_truth": self.source.to_dict()}
        if self.preferred_path:
            d["preferred_path"] = self.preferred_path
        if self.unresolved:
            d["unresolved"] = self.unresolved
        if self.conflicts:
            d["conflicts"] = self.conflicts
        return d


def _sot(type_: str, *, repo="", path="", ref="", confidence="medium",
         evidence=()) -> SourceOfTruth:
    return SourceOfTruth(type=type_, repository=repo, path=path, ref=ref,
                         confidence=confidence, evidence=list(evidence))


def resolve_one(resource: dict[str, Any],
                context: dict[str, Any] | None = None) -> Resolution:
    """Resolve the canonical edit location for one resource.

    `resource` fields used (any may be absent):
      resource_id, kind, annotations/labels (k8s), managed_by,
      argocd_app, argocd_repo/gitops_repo/gitops_path,
      tf_address + tf_repo/tf_path, crossplane xr/claim/composition,
      helm_release + chart_repo, provider, account, region.
    `context` may carry registries: gitops_apps{}, tf_modules{},
    helm_releases{}, crossplane_xrs{} keyed by name — each mapping to
    {repository, path, ref}.
    """
    ctx = context or {}
    rid = resource.get("resource_id") or resource.get("id") or ""
    ann = dict(resource.get("annotations") or {})
    labels = dict(resource.get("labels") or {})
    found: list[SourceOfTruth] = []
    conflicts: list[str] = []

    # --- GitOps: ArgoCD app owns the object → edit the Git repo -------
    app = resource.get("argocd_app") or ann.get(ARGOCD_INSTANCE, "").split("_")[0] \
        or (ann.get(ARGOCD_TRACKING, "") and resource.get("app_name"))
    if app:
        reg = (ctx.get("gitops_apps") or {}).get(app, {})
        repo = reg.get("repository") or resource.get("gitops_repo", "")
        path = reg.get("path") or resource.get("gitops_path", "")
        ref = reg.get("ref") or resource.get("gitops_ref", "HEAD")
        found.append(_sot("gitops", repo=repo, path=path, ref=ref,
                          confidence="high" if repo else "medium",
                          evidence=[f"argocd-app:{app}"]))
    elif any(k in labels for k in FLUXCD_LABELS):
        name = next(labels[k] for k in FLUXCD_LABELS if k in labels)
        reg = (ctx.get("flux_kustomizations") or {}).get(name, {})
        found.append(_sot("gitops", repo=reg.get("repository", ""),
                          path=reg.get("path", ""),
                          ref=reg.get("ref", "HEAD"),
                          confidence="high" if reg else "medium",
                          evidence=[f"flux-kustomization:{name}"]))

    # --- Terraform: resource tracked by state → edit the tf source ----
    tf_addr = next((resource.get(k) for k in TF_ADDRESS_ATTRS
                    if resource.get(k)), None)
    if tf_addr:
        mod = (ctx.get("tf_modules") or {}).get(tf_addr.split(".")[0], {})
        found.append(_sot("terraform",
                          repo=resource.get("tf_repo") or mod.get("repository", ""),
                          path=resource.get("tf_path") or mod.get("path", ""),
                          ref=resource.get("tf_ref") or mod.get("ref", "HEAD"),
                          confidence="high",
                          evidence=[f"tf-address:{tf_addr}"]))

    # --- Crossplane MR → XR/Composition ------------------------------
    if resource.get("crossplane_managed") or CROSSPLANE_CLAIM in ann:
        claim = resource.get("claim") or ann.get(CROSSPLANE_CLAIM, "")
        comp = resource.get("composition", "")
        ev = [f"crossplane-claim:{claim}"] if claim else ["crossplane-managed"]
        found.append(_sot("crossplane", path=comp or claim,
                          confidence="medium", evidence=ev))

    # --- Helm release → chart/values source ---------------------------
    if labels.get("app.kubernetes.io/managed-by") == "Helm" or \
            resource.get("helm_release"):
        rel = resource.get("helm_release") or labels.get(
            "app.kubernetes.io/instance", "")
        reg = (ctx.get("helm_releases") or {}).get(rel, {})
        found.append(_sot("helm", repo=reg.get("repository", ""),
                          path=reg.get("path", "") or f"charts/{rel}",
                          ref=reg.get("ref", "HEAD"), confidence="medium",
                          evidence=[f"helm-release:{rel}"] if rel else
                          ["helm-managed"]))

    if not found:
        # unmanaged → provider API is *possible* but never assumed safe
        if resource.get("managed_by") in ("manual", "console", "provider"):
            return Resolution(
                resource_id=rid,
                source=_sot("provider-api", confidence="low",
                            evidence=[f"managed_by:{resource['managed_by']}"]),
                preferred_path="direct-with-review")
        return Resolution(
            resource_id=rid,
            unresolved={"refusal": "PF-OPS-SOURCE-UNKNOWN",
                        "unlock": "provide ownership evidence (gitops app, "
                                  "tf address, helm release, crossplane claim) "
                                  "or mark managed_by explicitly"})

    if len(found) > 1:
        # §13 — precedence by evidence, not blind: gitops > terraform >
        # crossplane > helm, but *conflicts are recorded*, never silent.
        order = {"gitops": 0, "terraform": 1, "crossplane": 2, "helm": 3}
        found.sort(key=lambda s: order.get(s.type, 9))
        conflicts = [f"also-managed-by:{s.type}" for s in found[1:]]

    best = found[0]
    path = {"gitops": "gitops", "terraform": "terraform",
            "crossplane": "crossplane-config", "helm": "helm-values"}.get(
                best.type, "direct-with-review")
    return Resolution(resource_id=rid, source=best, preferred_path=path,
                      conflicts=conflicts)


def resolve(resources: list[dict[str, Any]],
            context: dict[str, Any] | None = None) -> list[Resolution]:
    return [resolve_one(r, context) for r in resources]


def unresolved_report(resolutions: list[Resolution]) -> dict[str, Any]:
    """§17 — unknown ownership is a human-review outcome, not a guess."""
    bad = [r for r in resolutions if r.unresolved]
    return {"total": len(resolutions), "resolved": len(resolutions) - len(bad),
            "unresolved": [r.to_dict() for r in bad],
            "action": "human-review-required" if bad else "none"}
