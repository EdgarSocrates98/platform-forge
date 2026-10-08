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
    AgentSpec(
        name="platform-planner", role="planner", domains=("all",),
        mission="turn a sealed TaskSpec into a loop choice + DAG draft",
        when_to_enter="a task needs orchestration beyond one specialist",
        when_not_to_enter="deterministic lookup; unsealed complex spec",
        allowed_verbs=("route", "graph deps"),
        allowed_capabilities=("platform.route",),
        never="executes stages; approves the spec it planned; invents "
              "capabilities not in the catalog",
        inputs=("task_spec", "routing_table", "orchestration_loops"),
        outputs=("plan", "dag_draft", "budget"),
        model_tier="standard",
        done_when="loop + DAG + envelope emitted or refused",
        escalation="platform-orchestrator",
    ),
    # --- coordinators (§28–34) ----------------------------------------
    AgentSpec(
        name="platform-incident-coordinator", role="coordinator",
        domains=("incident", "sre", "runtime"),
        mission="own incident scope, timeline, runtime evidence, "
                "change correlation and candidate causes",
        when_to_enter="incident/outage/regression question",
        when_not_to_enter="no runtime evidence; hypothetical postmortem",
        allowed_verbs=("observe", "correlate", "graph blast",
                       "route", "judge"),
        allowed_capabilities=("platform.observe", "platform.graph.query",
                              "platform.route"),
        never="declares 'last deploy = cause' without evidence; "
              "restarts/rolls back anything itself",
        inputs=("alerts", "spans", "deploy timeline", "task_spec"),
        delegates_to=("platform-sre-specialist",
                      "platform-kubernetes-specialist",
                      "platform-aws-specialist",
                      "platform-security-specialist",
                      "platform-graph-specialist",
                      "platform-gitops-specialist"),
        reviewers=("platform-evidence-reviewer",),
        verifier="platform-verifier",
        access="state-writer", write_scope="runs", model_tier="standard",
        max_parallelism=4,
        done_when="scope+timeline+candidate causes with evidence or "
                  "unresolved named; verifier closed",
        escalation="human operator",
    ),
    AgentSpec(
        name="platform-change-coordinator", role="coordinator",
        domains=("change", "ops"),
        mission="drive Finding→Recommendation→ChangeIntent→Simulation→"
                "Risk→Policy→Approval→Operation plan",
        when_to_enter="a proposed change needs governed review",
        when_not_to_enter="no finding/recommendation to govern; "
                          "execution request (refused)",
        allowed_verbs=("change review", "risk", "ops simulate",
                       "policy check", "route"),
        allowed_capabilities=("platform.ops.simulate", "platform.judge",
                              "platform.route"),
        never="executes the change — execution stays in the "
              "deterministic ops engine behind the human gate",
        inputs=("finding", "recommendation", "change_intent"),
        outputs=("operation_plan", "approval_requirement"),
        delegates_to=("platform-iac-specialist",
                      "platform-kubernetes-specialist",
                      "platform-gitops-specialist",
                      "platform-policy-specialist"),
        reviewers=("platform-operations-safety-reviewer",),
        verifier="platform-verifier",
        access="state-writer", write_scope="runs", model_tier="standard",
        max_parallelism=3,
        done_when="operation plan + approval requirement emitted; "
                  "human gate named",
        escalation="human operator",
    ),
    AgentSpec(
        name="platform-fleet-coordinator", role="coordinator",
        domains=("fleet",),
        mission="fleet-wide analysis: coverage, org graph, portfolio, "
                "capacity, cost, reliability, policy, golden paths",
        when_to_enter="fleet/portfolio/org-wide question",
        when_not_to_enter="single-repo question; no fleet inventory",
        allowed_verbs=("fleet analyze", "analyze drift", "finops costs",
                       "route"),
        allowed_capabilities=("platform.fleet.analyze",
                              "platform.route"),
        never="extrapolates one member to the whole fleet; skips "
              "coverage evidence",
        inputs=("workspace.yaml", "member observations"),
        delegates_to=("platform-fleet-specialist",
                      "platform-finops-specialist",
                      "platform-capacity-specialist",
                      "platform-sre-specialist",
                      "platform-security-specialist",
                      "platform-policy-specialist",
                      "platform-product-specialist",
                      "platform-optimization-coordinator"),
        reviewers=("platform-evidence-reviewer",
                   "platform-privacy-reviewer"),
        verifier="platform-verifier",
        access="state-writer", write_scope="runs", model_tier="standard",
        max_parallelism=6,
        done_when="coverage map + per-member evidence or unresolved "
                  "named; verifier closed",
        escalation="human operator",
    ),
    AgentSpec(
        name="platform-optimization-coordinator", role="coordinator",
        domains=("optimization", "finops", "capacity"),
        mission="coordinate finops/capacity/reliability/security/ops/"
                "golden-path/fleet/ai-platform signals into one "
                "OptimizationRecommendation",
        when_to_enter="cost/efficiency/rightsizing question or "
                      "optimization wave",
        when_not_to_enter="no measured baseline; request to execute "
                          "the recommendation",
        allowed_verbs=("finops costs", "observe capacity", "route",
                       "economy"),
        allowed_capabilities=("platform.finops.analyze",
                              "platform.route"),
        never="emits an ExecutionEnvelope — output is a "
              "OptimizationRecommendation; ChangeIntent only if "
              "accepted",
        inputs=("signals", "baselines"),
        outputs=("optimization_recommendation",),
        delegates_to=("platform-finops-specialist",
                      "platform-capacity-specialist",
                      "platform-sre-specialist",
                      "platform-security-specialist",
                      "platform-product-specialist",
                      "platform-fleet-specialist",
                      "platform-ai-infra-specialist"),
        reviewers=("platform-evidence-reviewer",
                   "platform-economy-reviewer"),
        verifier="platform-verifier",
        access="state-writer", write_scope="runs", model_tier="standard",
        max_parallelism=6,
        done_when="recommendation with measured baseline + expected "
                  "delta, or unresolved named",
        escalation="platform-change-coordinator",
    ),
    AgentSpec(
        name="platform-product-coordinator", role="coordinator",
        domains=("product", "dx", "golden-paths"),
        mission="golden paths, self-service, PlatformRequest, "
                "capability health, adoption, friction, maturity, DX",
        when_to_enter="adoption/DX/golden-path/maturity question",
        when_not_to_enter="pure infra question with no DX angle",
        allowed_verbs=("product", "capability list", "route"),
        allowed_capabilities=("platform.product", "platform.route"),
        never="invents adoption metrics; counts unmeasured usage as "
              "adoption",
        inputs=("capability health", "usage signals", "requests"),
        delegates_to=("platform-product-specialist",
                      "platform-fleet-specialist",
                      "platform-policy-specialist"),
        reviewers=("platform-evidence-reviewer",
                   "platform-privacy-reviewer"),
        verifier="platform-verifier",
        access="state-writer", write_scope="runs", model_tier="standard",
        max_parallelism=3,
        done_when="DX/maturity findings with measured signals or "
                  "unresolved named",
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
        domains=("sre", "slo", "incident", "capacity", "otel"),
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
    AgentSpec(
        name="platform-aws-specialist", role="specialist",
        domains=("aws", "cloud"),
        mission="read cloud inventory/IAM/VPC/EKS/RDS/S3 evidence",
        when_to_enter="cloud account/organization/resource question",
        when_not_to_enter="no inventory or live-snapshot evidence",
        allowed_verbs=("analyze iam", "analyze sbom", "inventory",
                       "judge"),
        allowed_capabilities=("platform.live.aws.snapshot",
                              "platform.analyze.security",
                              "platform.judge"),
        required_evidence=("fact_ids", "coverage"),
        never="calls provider APIs itself — snapshots arrive through "
              "adapters; treats a partial inventory as complete",
        inputs=("inventory", "iam policies", "config snapshots"),
        done_when="facts+judge emitted with coverage or unresolved "
                  "named",
    ),
    AgentSpec(
        name="platform-crossplane-specialist", role="specialist",
        domains=("crossplane",),
        mission="read XRD/XR/Claim/Composition/provider evidence",
        when_to_enter="Crossplane artifacts or managed-resource question",
        when_not_to_enter="no Crossplane artifacts in scope",
        allowed_verbs=("analyze crossplane", "judge"),
        allowed_capabilities=("platform.analyze.crossplane",
                              "platform.judge"),
        required_evidence=("fact_ids",),
        never="treats a Claim as provisioned without observed state",
        inputs=("xrd", "compositions", "claims"),
        done_when="facts+judge emitted or unresolved named",
    ),
    AgentSpec(
        name="platform-fleet-specialist", role="specialist",
        domains=("fleet",),
        mission="fleet coverage, org topology, multi-cluster/"
                "multi-account portfolio evidence",
        when_to_enter="fleet/member/portfolio question",
        when_not_to_enter="no workspace.yaml members or observations",
        allowed_verbs=("fleet analyze", "fleet status",
                       "analyze drift"),
        allowed_capabilities=("platform.fleet.analyze",),
        required_evidence=("coverage",),
        never="extrapolates one member to the fleet; hides uncovered "
              "members",
        inputs=("member observations", "workspace.yaml"),
        done_when="coverage map emitted; uncovered members named",
    ),
    AgentSpec(
        name="platform-policy-specialist", role="specialist",
        domains=("policy", "governance"),
        mission="OPA/Rego/Kyverno/CEL evidence, policy analytics, "
                "exceptions, approval rules, autonomy boundaries",
        when_to_enter="policy/governance/exceptions question",
        when_not_to_enter="no policy artifacts; approval decision "
                          "itself (governance gate)",
        allowed_verbs=("policy check", "judge", "explain"),
        allowed_capabilities=("platform.judge", "platform.policy"),
        required_evidence=("fact_ids",),
        never="approves or denies a change — it reads policy; the "
              "human gate decides",
        inputs=("policies", "exceptions", "approvals"),
        done_when="policy findings emitted or unresolved named",
    ),
    AgentSpec(
        name="platform-capacity-specialist", role="specialist",
        domains=("capacity", "reliability"),
        mission="capacity/headroom/quota/failure-domain/reliability "
                "hotspot evidence",
        when_to_enter="capacity/headroom/quota/reliability question",
        when_not_to_enter="no capacity or telemetry facts",
        allowed_verbs=("observe capacity", "observe slo", "judge"),
        allowed_capabilities=("platform.observe", "platform.judge"),
        required_evidence=("fact_ids", "freshness"),
        never="projects capacity without measured headroom",
        inputs=("quota facts", "usage metrics", "topology"),
        done_when="facts+judge emitted or unresolved named",
    ),
    AgentSpec(
        name="platform-product-specialist", role="specialist",
        domains=("product", "dx"),
        mission="self-service/golden-path/developer-friction/capability-"
                "health/maturity evidence",
        when_to_enter="DX/adoption/golden-path question",
        when_not_to_enter="no usage or request signals",
        allowed_verbs=("product", "capability list"),
        allowed_capabilities=("platform.product",),
        required_evidence=("fact_ids",),
        never="invents adoption; counts intention as usage",
        inputs=("usage signals", "requests", "capability health"),
        done_when="DX findings emitted or unresolved named",
    ),
    AgentSpec(
        name="platform-ai-infra-specialist", role="specialist",
        domains=("ai", "gpu"),
        mission="AI infrastructure only: GPU/MIG/model-serving/AI "
                "capacity/cost/SLO evidence",
        when_to_enter="GPU/model-serving/ai-capacity question",
        when_not_to_enter="model development, prompt engineering or "
                          "RAG architecture (explicitly out of scope)",
        allowed_verbs=("analyze ai", "finops costs", "judge"),
        allowed_capabilities=("platform.analyze.ai",
                              "platform.finops.analyze"),
        required_evidence=("fact_ids",),
        never="advises on model quality/prompts; claims GPU savings "
              "without measured utilization",
        inputs=("gpu inventory", "serving metrics", "cost rows"),
        done_when="facts+judge emitted or unresolved named",
    ),
    AgentSpec(
        name="platform-federation-specialist", role="specialist",
        domains=("federation",),
        mission="ForgeNode/export-policy/summary-exchange/authority-"
                "boundary/fleet-federation evidence",
        when_to_enter="federation/forgenode/sibling-forge question",
        when_not_to_enter="no federation config or export policy",
        allowed_verbs=("federation status", "federation export",
                       "judge"),
        allowed_capabilities=("platform.federation",),
        required_evidence=("fact_ids",),
        never="exports raw facts across the authority boundary — "
              "summaries only, per export policy",
        inputs=("forgenode configs", "export policies"),
        done_when="federation findings emitted or unresolved named",
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
        name="platform-task-spec-reviewer", role="reviewer",
        domains=("tasks",),
        mission="review and seal TaskSpecs before orchestration",
        when_to_enter="a draft TaskSpec exists",
        when_not_to_enter="spec already sealed; spec it wrote itself",
        allowed_verbs=("route", "capability check"),
        allowed_capabilities=("platform.route",),
        never="seals its own spec; edits intent — it rejects, "
              "it does not rewrite",
        inputs=("draft_spec",),
        outputs=("seal", "rejection", "questions"),
        model_tier="fast",
        done_when="spec sealed with hash or rejected with reasons",
    ),
    AgentSpec(
        name="platform-adversarial-critic", role="critic",
        domains=("plans",),
        mission="attack the plan before acceptance on the §22 axes",
        when_to_enter="a DAG draft exists and has not run yet",
        when_not_to_enter="post-run closure — that is the verifier's job",
        allowed_verbs=("judge",),
        allowed_capabilities=("platform.judge",),
        never="verifies — it finds how this could be wrong, "
              "not that it is right",
        inputs=("plan", "spec"),
        outputs=("attacks", "open_risks"),
        model_tier="critical-review",
        done_when="every attack axis answered ok|risk",
    ),
    AgentSpec(
        name="platform-verifier", role="verifier", domains=("closure",),
        mission="independently check a run before closure",
        when_to_enter="a run record is complete",
        when_not_to_enter="it produced any output in the run it is "
                          "verifying (independence)",
        allowed_verbs=("judge", "diff", "graph query"),
        allowed_capabilities=("platform.judge",),
        required_evidence=("fact_ids",),
        never="verifies its own work; upgrades a refuted claim; "
              "accepts missing criteria as passed",
        inputs=("run_record", "spec", "evidence_index"),
        outputs=("verdict", "receipt"),
        model_tier="critical-review",
        done_when="confirmed|unresolved verdict + receipt emitted",
    ),
    AgentSpec(
        name="platform-release-guardian", role="guardian",
        domains=("release",),
        mission="deterministic closure review — READY or blockers",
        when_to_enter="release/freeze question",
        when_not_to_enter="any signal unmeasured — missing is a blocker",
        allowed_verbs=("validate", "status", "evals run", "lab run-all"),
        allowed_capabilities=("platform.validate",),
        never="runs the gates itself; calls unmeasured signals passed",
        inputs=("gate_signals", "receipts"),
        outputs=("verdict", "blockers"),
        model_tier="deterministic",
        done_when="READY or an explicit blocker list emitted",
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
