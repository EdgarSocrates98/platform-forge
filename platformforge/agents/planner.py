"""platform-planner — turn a user goal into a TaskSpec (§14).

Deterministic intake: domain inference is a declared keyword table, not
a model call. The planner emits a *draft* spec — it never executes,
never approves, never verifies (§15).
"""

from __future__ import annotations

from platformforge.agents.contracts import PlatformTaskSpec
from platformforge.agents.taskspec import MUTATING_CAPS
from platformforge.models.base import stable_id

# intent keyword → domain. Declared data: an operator can audit why a
# domain was inferred; nothing is hidden in a prompt.
_DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "iac": ("terraform", "hcl", "tofu", "plan", "state", "iac",
            "module"),
    "k8s": ("kubernetes", "k8s", "manifest", "helm", "kustomize",
            "deployment", "pod", "cluster", "workload"),
    "gitops": ("argocd", "flux", "gitops", "rollout"),
    "aws": ("aws", "iam", "s3", "ec2", "vpc", "eks", "rds"),
    "crossplane": ("crossplane", "xrd", "composition", "claim"),
    "sre": ("slo", "sli", "incident", "latency", "burn", "otel",
            "reliability", "capacity", "outage"),
    "security": ("security", "secret", "sbom", "supply", "cve",
                 "signature", "slsa", "exposure", "vulnerability"),
    "finops": ("cost", "finops", "billing", "spend", "savings",
               "rightsizing", "focus"),
    "graph": ("dependency", "blast", "impact", "graph", "path"),
    "fleet": ("fleet", "clusters", "accounts", "org", "portfolio"),
    "policy": ("policy", "opa", "kyverno", "cel", "governance",
               "compliance"),
    "product": ("golden", "self-service", "dx", "adoption",
                "developer", "maturity"),
    "ai": ("gpu", "mig", "model serving", "ai platform", "llm infra"),
    "federation": ("federation", "forgenode", "sibling forge",
                   "export policy"),
}

_SCOPE_KEYWORDS = {
    "fleet": ("fleet", "organization", "org-wide", "all clusters",
              "all accounts"),
    "runtime": ("incident", "running", "live", "production", "slo"),
    "change": ("change", "migrate", "upgrade", "deploy", "apply",
               "rollout"),
}

_EVIDENCE_BY_DOMAIN = {
    "iac": ("iac artifacts", "plan facts", "state facts"),
    "k8s": ("manifest facts", "coverage"),
    "aws": ("cloud inventory facts", "coverage"),
    "sre": ("telemetry facts", "freshness"),
    "security": ("security facts", "sbom/material"),
    "finops": ("cost facts", "denominators"),
    "fleet": ("member observations", "coverage"),
    "graph": ("graph with provenance",),
}


def infer_domains(intent: str) -> tuple[str, ...]:
    terms = intent.lower()
    out = [d for d, kws in _DOMAIN_KEYWORDS.items()
           if any(k in terms for k in kws)]
    return tuple(sorted(out))


def infer_scope(intent: str) -> str:
    terms = intent.lower()
    for scope, kws in _SCOPE_KEYWORDS.items():
        if any(k in terms for k in kws):
            return scope
    return "repo"


def infer_complexity(intent: str, domains: tuple[str, ...],
                     scope: str) -> str:
    terms = intent.lower()
    if scope == "fleet" or len(domains) >= 3 or \
            any(w in terms for w in ("entire", "whole", "audit",
                                     "across")):
        return "high"
    if len(domains) == 2 or scope in ("runtime", "change"):
        return "medium"
    return "low"


def plan(intent: str, *, domains: tuple[str, ...] | None = None,
         risk: str = "low", complexity: str | None = None,
         autonomy: str = "read-only",
         acceptance_criteria: tuple[str, ...] | None = None,
         rollback_requirement: str = "none") -> PlatformTaskSpec:
    """intent → draft PlatformTaskSpec. Caller reviews + seals it."""
    doms = domains or infer_domains(intent)
    scope = infer_scope(intent)
    cx = complexity or infer_complexity(intent, doms, scope)
    if risk == "low" and scope == "change":
        risk = "high"
    ev = sorted({e for d in doms
                 for e in _EVIDENCE_BY_DOMAIN.get(d, ("facts",))}
                | {"coverage", "freshness"})
    budget = {"low": "small", "medium": "standard",
              "high": "deep"}.get(cx, "standard")
    if risk in ("high", "critical"):
        budget = "critical" if risk == "critical" else "deep"
    spec = PlatformTaskSpec(
        task_id=stable_id("PF-TASK", intent, ",".join(doms), scope),
        intent=intent, scope=scope, domains=doms, risk=risk,
        complexity=cx, evidence_requirements=tuple(ev),
        acceptance_criteria=acceptance_criteria
        or (("every domain answer carries fact_ids or a named "
             "unresolved"), "independent verifier closes the run"),
        autonomy=autonomy,
        forbidden_capabilities=MUTATING_CAPS,
        rollback_requirement=rollback_requirement, budget=budget)
    return spec
