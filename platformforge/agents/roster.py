"""Canonical agent roster — one definition, generated host mirrors.

AgentSpec v2 (cycle5.1 §6–§11): every agent declares what it does AND
what it does not do (negative capability), typed access tier, model
tier (never a provider name), budgets, delegation boundary, reviewers
and verifier. Coordinators/orchestrators dispatch; specialists and
executors never spawn uncontrolled trees.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from platformforge.agents.contracts import ACCESS_TIERS, MODEL_TIERS, ROLES, SCHEMA_AGENT_SPEC, WRITE_SCOPES


@dataclass(frozen=True)
class AgentSpec:
    """Canonical agent contract — `platformforge/agent-spec/v1`.

    name                 unique slug (platform-* or pf-*)
    role                 orchestrator|planner|coordinator|specialist|
                         executor|reviewer|critic|referee|verifier|guardian
    domains              capability domains it reasons about
    mission              one-line responsibility
    when_to_enter        activation condition (used by routing + mirrors)
    when_not_to_enter    explicit non-trigger (negative capability #1)
    inputs / outputs     accepted artifacts / emitted contract
    required_evidence    evidence classes it must cite or stay unresolved
    allowed_verbs        platformforge verbs it may invoke
    allowed_tools        host tool classes (mapped per-host, §106)
    allowed_capabilities capability ids it may request (§102–103)
    access               ACCESS_TIERS value
    write_scope          WRITE_SCOPES value — what it may persist
    model_tier           MODEL_TIERS value — tier, not provider
    max_context_budget   context bytes ceiling per invocation
    max_tool_calls       tool call ceiling per invocation
    max_parallelism      max concurrent sub-steps it may request
    delegates_to         agents it may hand off to
    cannot_delegate_to   delegation boundary (explicit denial)
    reviewers            mandatory reviewers of its output
    verifier             agent that closes the loop (never itself)
    escalation           where it escalates when stuck
    done_when            completion contract
    never                hard prohibitions (negative capability #2)
    """

    name: str
    role: str
    domains: tuple[str, ...]
    mission: str = ""
    when_to_enter: str = ""
    when_not_to_enter: str = ""
    inputs: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ("findings", "unresolved", "evidence_ids")
    required_evidence: tuple[str, ...] = ()
    allowed_verbs: tuple[str, ...] = ()
    allowed_tools: tuple[str, ...] = ()
    allowed_capabilities: tuple[str, ...] = ()
    access: str = "read-only"
    write_scope: str = "none"
    model_tier: str = "standard"
    max_context_budget: int = 120_000
    max_tool_calls: int = 24
    max_parallelism: int = 1
    delegates_to: tuple[str, ...] = ()
    cannot_delegate_to: tuple[str, ...] = ()
    reviewers: tuple[str, ...] = ()
    verifier: str = ""
    escalation: str = ""
    done_when: str = ""
    never: str = ""

    # --- legacy accessors (pre-v2 field names) ------------------------
    @property
    def when(self) -> str:
        return self.when_to_enter

    @property
    def verbs(self) -> tuple[str, ...]:
        return self.allowed_verbs

    @property
    def executors(self) -> tuple[str, ...]:
        return self.delegates_to

    def contract_errors(self) -> list[str]:
        """Deterministic lint of a single spec — the agents-contract gate."""
        bad = []
        if self.role not in ROLES:
            bad.append(f"role {self.role!r} not in {ROLES}")
        if self.access not in ACCESS_TIERS:
            bad.append(f"access {self.access!r} not in {ACCESS_TIERS}")
        if self.write_scope not in WRITE_SCOPES:
            bad.append(f"write_scope {self.write_scope!r} not in {WRITE_SCOPES}")
        if self.model_tier not in MODEL_TIERS:
            bad.append(f"model_tier {self.model_tier!r} not in {MODEL_TIERS}")
        if not self.when_to_enter:
            bad.append("missing when_to_enter")
        if not self.when_not_to_enter:
            bad.append("missing when_not_to_enter (negative capability)")
        if not self.never:
            bad.append("missing never (negative capability)")
        if self.role in ("orchestrator", "coordinator") \
                and not self.delegates_to:
            bad.append("coordinator without delegates_to")
        if self.role == "executor" and self.delegates_to:
            bad.append("executor must not delegate (§66)")
        if self.role in ("specialist", "reviewer", "critic",
                         "verifier", "executor") and self.access != "read-only":
            bad.append("only orchestrator/coordinator paths may hold "
                       "non-read-only access")
        if self.verifier and self.verifier == self.name:
            bad.append("agent cannot verify itself (§21)")
        return bad

    def to_dict(self) -> dict[str, Any]:
        return {"schema": SCHEMA_AGENT_SPEC,
                "name": self.name, "role": self.role,
                "domains": list(self.domains), "mission": self.mission,
                "when_to_enter": self.when_to_enter,
                "when_not_to_enter": self.when_not_to_enter,
                "inputs": list(self.inputs), "outputs": list(self.outputs),
                "required_evidence": list(self.required_evidence),
                "allowed_verbs": list(self.allowed_verbs),
                "allowed_tools": list(self.allowed_tools),
                "allowed_capabilities": list(self.allowed_capabilities),
                "access": self.access, "write_scope": self.write_scope,
                "model_tier": self.model_tier,
                "max_context_budget": self.max_context_budget,
                "max_tool_calls": self.max_tool_calls,
                "max_parallelism": self.max_parallelism,
                "delegates_to": list(self.delegates_to),
                "cannot_delegate_to": list(self.cannot_delegate_to),
                "reviewers": list(self.reviewers),
                "verifier": self.verifier, "escalation": self.escalation,
                "done_when": self.done_when, "never": self.never}


AGENTS: dict[str, AgentSpec] = {a.name: a for a in [
    # --- coordinators ------------------------------------------------
    AgentSpec(
        name="platform-orchestrator", role="orchestrator",
        domains=("all",),
        mission="decompose cross-domain platform questions into "
                "specialist work and collect evidence",
        when_to_enter="cross-domain platform question — "
                      "'analise minha plataforma'",
        when_not_to_enter="single-domain question answerable by one "
                          "specialist; deterministic lookup",
        allowed_verbs=("inspect", "analyze", "judge", "graph", "route",
                       "observe", "finops", "product"),
        allowed_capabilities=("platform.inspect", "platform.analyze",
                              "platform.judge", "platform.graph.query"),
        never="executes analysis itself; mutates; picks specialists by "
              "vibe instead of routing.yaml; declares itself done",
        inputs=("intent", "repo_root"),
        delegates_to=("platform-iac-specialist",
                      "platform-kubernetes-specialist",
                      "platform-gitops-specialist",
                      "platform-sre-specialist",
                      "platform-finops-specialist",
                      "platform-security-specialist",
                      "platform-graph-specialist"),
        reviewers=("platform-evidence-reviewer",),
        verifier="platform-verifier",
        access="state-writer", write_scope="runs",
        model_tier="standard", max_parallelism=4,
        done_when="every specialist answered or named unresolved, "
                  "evidence reviewer passed, handoff complete",
        escalation="human operator",
    ),
    # --- specialists --------------------------------------------------
    AgentSpec(
        name="platform-iac-specialist", role="specialist", domains=("iac", "terraform"),
        mission="read IaC artifacts into facts; judge them against rules",
        when_to_enter="HCL/plan/state artifacts present or IaC question",
        when_not_to_enter="no IaC artifacts in scope; live cloud query",
        allowed_verbs=("analyze iac", "analyze plan", "analyze state",
                       "analyze drift", "judge"),
        allowed_capabilities=("platform.analyze.iac", "platform.judge"),
        required_evidence=("fact_ids",),
        never="applies plans; touches cloud APIs; treats plan as observed",
        inputs=("*.tf", "plan.json", "state.json"),
        done_when="facts+judge emitted or unresolved named with the "
                  "missing artifact",
    ),
    AgentSpec(
        name="platform-kubernetes-specialist", role="specialist", domains=("k8s", "helm"),
        mission="read manifests/Helm/Kustomize into facts; judge them",
        when_to_enter="manifests/Helm/Kustomize present or workload question",
        when_not_to_enter="live cluster question without an observation "
                          "envelope",
        allowed_verbs=("analyze k8s", "judge", "graph deps",
                       "graph blast"),
        allowed_capabilities=("platform.analyze.k8s", "platform.judge",
                              "platform.graph.query"),
        required_evidence=("fact_ids",),
        never="kubectl apply; mutates clusters; infers runtime state "
              "from manifests alone",
        inputs=("*.yaml manifests",),
        done_when="facts+judge emitted or unresolved named",
    ),
    AgentSpec(
        name="platform-gitops-specialist", role="specialist",
        domains=("gitops", "cicd"),
        mission="read ArgoCD/Flux/pipeline artifacts; check delivery path",
        when_to_enter="ArgoCD/Flux/GHA artifacts or delivery-path question",
        when_not_to_enter="no delivery artifacts; commit/rollback request",
        allowed_verbs=("analyze gitops", "analyze gha", "judge"),
        allowed_capabilities=("platform.analyze.gitops", "platform.judge"),
        required_evidence=("fact_ids",),
        never="commits to git; triggers pipelines; treats desired as "
              "observed",
        inputs=("argocd apps", "flux resources", "workflows"),
        done_when="facts+judge emitted or unresolved named",
    ),
    AgentSpec(
        name="platform-sre-specialist", role="specialist",
        domains=("slo", "incident", "capacity", "otel"),
        mission="interpret telemetry/SLO/incident evidence",
        when_to_enter="reliability/latency/incident question or telemetry "
                      "present",
        when_not_to_enter="no telemetry scope; root-cause claim without "
                          "evidence",
        allowed_verbs=("observe slo", "observe otel", "observe incident",
                       "observe capacity", "judge"),
        allowed_capabilities=("platform.observe", "platform.judge"),
        required_evidence=("fact_ids", "freshness"),
        never="declares causation from correlation; invents SLOs",
        inputs=("spans", "alerts", "slo contracts", "metrics dumps"),
        done_when="facts+judge emitted or unresolved named",
    ),
    AgentSpec(
        name="platform-finops-specialist", role="specialist", domains=("finops",),
        mission="decompose cost evidence into findings",
        when_to_enter="cost/allocation/unit-economics question or billing "
                      "export",
        when_not_to_enter="no billing data; savings claim without baseline",
        allowed_verbs=("finops costs", "finops allocate", "finops graph",
                       "finops focus"),
        allowed_capabilities=("platform.finops.analyze",),
        required_evidence=("fact_ids", "denominators"),
        never="claims savings without a measured baseline",
        inputs=("billing export", "cost rows"),
        done_when="facts+judge emitted or unresolved named",
    ),
    AgentSpec(
        name="platform-security-specialist", role="specialist", domains=("security",),
        mission="analyze IAM/SBOM/supply-chain/secrets evidence",
        when_to_enter="IAM/SBOM/supply-chain/secrets question",
        when_not_to_enter="request to print or emit secret material",
        allowed_verbs=("analyze iam", "analyze sbom", "analyze secrets",
                       "analyze supply", "judge"),
        allowed_capabilities=("platform.analyze.security",
                              "platform.judge"),
        required_evidence=("fact_ids",),
        never="prints secret values; verifies signatures offline only "
              "against provided material",
        inputs=("policies", "sboms", "artifact inventories"),
        done_when="facts+judge emitted or unresolved named",
    ),
    AgentSpec(
        name="platform-graph-specialist", role="specialist", domains=("graph",),
        mission="build and query the platform graph",
        when_to_enter="dependency/impact/blast-radius question",
        when_not_to_enter="no facts to build from",
        allowed_verbs=("graph build", "graph deps", "graph dependents",
                       "graph blast", "graph paths", "graph gaps",
                       "graph diff"),
        allowed_capabilities=("platform.graph.build",
                              "platform.graph.query"),
        required_evidence=("fact_ids",),
        never="treats proximity as causality",
        inputs=("facts", "snapshots"),
        done_when="graph answer emitted with provenance or unresolved "
                  "named",
    ),
    # --- reviewers / referee ------------------------------------------
    AgentSpec(
        name="platform-evidence-reviewer", role="reviewer", domains=("evidence",),
        mission="gate conclusions on cited evidence",
        when_to_enter="before any conclusion ships",
        when_not_to_enter="no conclusion produced yet",
        allowed_verbs=("judge", "status"),
        allowed_capabilities=("platform.judge",),
        required_evidence=("fact_ids",),
        never="accepts findings with empty evidence",
        inputs=("findings", "facts"),
        outputs=("verdict", "missing_evidence"),
        model_tier="critical-review",
        done_when="every finding carries evidence or is marked "
                  "unresolved",
    ),
    AgentSpec(
        name="platform-debate-referee", role="referee", domains=("conflicts",),
        mission="adjudicate specialist disagreement on declared axes",
        when_to_enter="two specialists disagree",
        when_not_to_enter="single uncontested position; no evidence on "
                          "either side",
        allowed_verbs=("route", "judge"),
        allowed_capabilities=("platform.judge",),
        never="averages positions; ranks by vibes — evidence tier decides",
        inputs=("competing findings",),
        outputs=("adjudication", "receipt"),
        model_tier="critical-review",
        done_when="winner/tied/unresolved returned with receipt",
    ),
    AgentSpec(
        name="platform-economy-reviewer", role="reviewer", domains=("economy",),
        mission="audit token/context spend claims",
        when_to_enter="context spend is questioned",
        when_not_to_enter="no ledger/pack data to measure",
        allowed_verbs=("economy", "tokens stats", "tokens ledger"),
        allowed_capabilities=("platform.economy",),
        required_evidence=("ledger",),
        never="claims token savings without measured bytes",
        inputs=("ledger", "packs"),
        outputs=("report",),
        done_when="spend reported with measured bytes or unresolved "
                  "named",
    ),
]}


# Legacy names still resolve — one source of truth, no silent drift.
LEGACY_NAMES: dict[str, str] = {
    "platform-coordinator": "platform-orchestrator",
    "iac-analyst": "platform-iac-specialist",
    "k8s-analyst": "platform-kubernetes-specialist",
    "gitops-analyst": "platform-gitops-specialist",
    "sre-analyst": "platform-sre-specialist",
    "finops-analyst": "platform-finops-specialist",
    "security-analyst": "platform-security-specialist",
    "graph-analyst": "platform-graph-specialist",
    "evidence-reviewer": "platform-evidence-reviewer",
    "consistency-referee": "platform-debate-referee",
    "economy-reviewer": "platform-economy-reviewer",
    # routing.yaml v1 names (pre-5.1 drift) resolve to canonical agents
    "incident-coordinator": "platform-incident-coordinator",
    "security-reviewer": "platform-security-reviewer",
    "architecture-reviewer": "platform-architecture-reviewer",
    "change-risk-reviewer": "platform-operations-safety-reviewer",
    "finops-coordinator": "platform-finops-specialist",
    "kubernetes-specialist": "platform-kubernetes-specialist",
}


def resolve(name: str) -> AgentSpec | None:
    """Canonical-name lookup; legacy aliases resolve with no ambiguity."""
    return AGENTS.get(name) or AGENTS.get(LEGACY_NAMES.get(name, ""))


def coordinator_for(domain: str) -> AgentSpec | None:
    for a in AGENTS.values():
        if a.role == "specialist" and domain in a.domains:
            return a
    return AGENTS["platform-orchestrator"]
