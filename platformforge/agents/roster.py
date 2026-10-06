"""Canonical agent roster — one definition, three generated mirrors.

Contract per agent: when_to_enter, never_does, inputs, method (verbs),
output contract, access tier. Coordinators dispatch executors; executors
never dispatch.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AgentSpec:
    name: str
    role: str                      # coordinator | specialist | reviewer | referee
    domains: tuple[str, ...]
    access: str = "read-only"      # read-only | state-writer | writer
    verbs: tuple[str, ...] = ()    # allowed platformforge verbs
    when: str = ""
    never: str = ""
    inputs: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ("findings", "unresolved", "evidence_ids")
    executors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "role": self.role,
                "domains": list(self.domains), "access": self.access,
                "verbs": list(self.verbs), "when": self.when,
                "never": self.never, "inputs": list(self.inputs),
                "outputs": list(self.outputs),
                "executors": list(self.executors)}


AGENTS: dict[str, AgentSpec] = {a.name: a for a in [
    AgentSpec(
        name="platform-coordinator", role="coordinator",
        domains=("all",),
        verbs=("inspect", "analyze", "judge", "graph", "route", "observe",
               "finops", "product"),
        when="cross-domain platform question — 'analise minha plataforma'",
        never="executes analysis itself; mutates; picks specialists by vibe "
              "instead of routing.yaml",
        inputs=("intent", "repo_root"),
        executors=("iac-analyst", "k8s-analyst", "gitops-analyst",
                   "sre-analyst", "finops-analyst", "security-analyst",
                   "graph-analyst"),
    ),
    AgentSpec(
        name="iac-analyst", role="specialist", domains=("iac", "terraform"),
        verbs=("analyze iac", "analyze plan", "analyze state",
               "analyze drift", "judge"),
        when="HCL/plan/state artifacts present or IaC question",
        never="applies plans; touches cloud APIs",
        inputs=("*.tf", "plan.json", "state.json"),
    ),
    AgentSpec(
        name="k8s-analyst", role="specialist", domains=("k8s", "helm"),
        verbs=("analyze k8s", "judge", "graph deps", "graph blast"),
        when="manifests/Helm/Kustomize present or workload question",
        never="kubectl apply; mutates clusters",
        inputs=("*.yaml manifests",),
    ),
    AgentSpec(
        name="gitops-analyst", role="specialist",
        domains=("gitops", "cicd"),
        verbs=("analyze gitops", "analyze gha", "judge"),
        when="ArgoCD/Flux/GHA artifacts or delivery-path question",
        never="commits to git; triggers pipelines",
        inputs=("argocd apps", "flux resources", "workflows"),
    ),
    AgentSpec(
        name="sre-analyst", role="specialist",
        domains=("slo", "incident", "capacity", "otel"),
        verbs=("observe slo", "observe otel", "observe incident",
               "observe capacity", "judge"),
        when="reliability/latency/incident question or telemetry present",
        never="declares causation from correlation; invents SLOs",
        inputs=("spans", "alerts", "slo contracts", "metrics dumps"),
    ),
    AgentSpec(
        name="finops-analyst", role="specialist", domains=("finops",),
        verbs=("finops costs", "finops allocate", "finops graph",
               "finops focus"),
        when="cost/allocation/unit-economics question or billing export",
        never="claims savings without a measured baseline",
        inputs=("billing export", "cost rows"),
    ),
    AgentSpec(
        name="security-analyst", role="specialist", domains=("security",),
        verbs=("analyze iam", "analyze sbom", "analyze secrets",
               "analyze supply", "judge"),
        when="IAM/SBOM/supply-chain/secrets question",
        never="prints secret values; verifies signatures offline",
        inputs=("policies", "sboms", "artifact inventories"),
    ),
    AgentSpec(
        name="graph-analyst", role="specialist", domains=("graph",),
        verbs=("graph build", "graph deps", "graph dependents",
               "graph blast", "graph paths", "graph gaps", "graph diff"),
        when="dependency/impact/blast-radius question",
        never="treats proximity as causality",
        inputs=("facts", "snapshots"),
    ),
    AgentSpec(
        name="evidence-reviewer", role="reviewer", domains=("evidence",),
        verbs=("judge", "status"),
        when="before any conclusion ships",
        never="accepts findings with empty evidence",
        inputs=("findings", "facts"),
        outputs=("verdict", "missing_evidence"),
    ),
    AgentSpec(
        name="consistency-referee", role="referee", domains=("conflicts",),
        verbs=("route", "judge"),
        when="two specialists disagree",
        never="averages positions; ranks by vibes — evidence tier decides",
        inputs=("competing findings",),
        outputs=("adjudication", "receipt"),
    ),
    AgentSpec(
        name="economy-reviewer", role="reviewer", domains=("economy",),
        verbs=("economy", "tokens stats", "tokens ledger"),
        when="context spend is questioned",
        never="claims token savings without measured bytes",
        inputs=("ledger", "packs"),
        outputs=("report",),
    ),
]}


def coordinator_for(domain: str) -> AgentSpec | None:
    for a in AGENTS.values():
        if a.role == "specialist" and domain in a.domains:
            return a
    return AGENTS["platform-coordinator"]
