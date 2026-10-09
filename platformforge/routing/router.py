"""Router V2 — adaptive routing as a full dispatch decision (§81–91).

Route = f(task type, domains, complexity, risk, blast radius, security
sensitivity, production, evidence completeness, coverage, freshness,
expected provider cost, expected token cost, mutability, fleet scope,
incident status). The table lives in rules/catalog/routing.yaml —
data, not judgment.

Output (§82): mode, coordinator, specialists, reviewers, verifier,
execution DAG, budget, reasons, fallbacks — never just an agent list.

Modes (§83): deterministic | single-specialist | multi-specialist |
coordinated | debate | critical-review. Default is deterministic (§84);
debate opens only on conflict / high risk+low confidence / explicit
comparison (§88); critical-review is mandatory for production mutation,
IAM, security, destructive data changes, large fleet optimization (§89).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class TaskSignal:
    """§81 — the routing signals. v1 fields kept for compatibility."""
    task_type: str = "analysis"        # lint|analysis|review|incident|architecture|change
    domains: list[str] = field(default_factory=list)
    complexity: str = "low"            # low|medium|high
    risk: str = "low"                  # low|medium|high|critical
    blast_radius: str = "local"        # local|service|platform|org
    security_sensitive: bool = False
    evidence_available: bool = True
    production: bool = False
    expected_cost: str = "low"             # provider cost: low|medium|high
    evidence_completeness: float = 1.0     # 0-1 measured fraction
    # --- v2 signals (§81) ------------------------------------------
    coverage: float = 1.0                  # fraction of scope covered
    freshness: str = "current"             # current|stale|unknown
    expected_token_cost: str = "low"       # low|medium|high
    mutability: str = "read"               # read|propose|mutate
    fleet_scope: bool = False
    incident_status: str = ""              # ""|active|mitigated
    conflict: bool = False                 # specialists disagree (§88)
    comparison: bool = False               # user asked to compare (§88)
    destructive: bool = False              # destructive data change (§89)
    optimization: bool = False             # optimization task (§89 fleet)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> TaskSignal:
        return cls(**{k: v for k, v in d.items()
                      if k in cls.__dataclass_fields__})


# domain → canonical specialist. Declared data, audit-friendly.
DOMAIN_SPECIALIST = {
    "iac": "platform-iac-specialist", "terraform": "platform-iac-specialist",
    "k8s": "platform-kubernetes-specialist",
    "kubernetes": "platform-kubernetes-specialist",
    "helm": "platform-kubernetes-specialist",
    "gitops": "platform-gitops-specialist", "cicd": "platform-gitops-specialist",
    "aws": "platform-aws-specialist", "cloud": "platform-aws-specialist",
    "crossplane": "platform-crossplane-specialist",
    "sre": "platform-sre-specialist", "slo": "platform-sre-specialist",
    "incident": "platform-sre-specialist", "otel": "platform-sre-specialist",
    "security": "platform-security-specialist",
    "finops": "platform-finops-specialist", "cost": "platform-finops-specialist",
    "graph": "platform-graph-specialist",
    "fleet": "platform-fleet-specialist",
    "policy": "platform-policy-specialist",
    "governance": "platform-policy-specialist",
    "capacity": "platform-capacity-specialist",
    "reliability": "platform-capacity-specialist",
    "product": "platform-product-specialist", "dx": "platform-product-specialist",
    "ai": "platform-ai-infra-specialist", "gpu": "platform-ai-infra-specialist",
    "federation": "platform-federation-specialist",
}

# coordinator per task shape (coordinators.py COORDINATOR_LOOPS echo)
TASK_COORDINATOR = {
    "incident": "platform-incident-coordinator",
    "change": "platform-change-coordinator",
    "fleet": "platform-fleet-coordinator",
    "optimization": "platform-optimization-coordinator",
    "product": "platform-product-coordinator",
    "architecture": "platform-orchestrator",
    "analysis": "platform-orchestrator",
}

BUILTIN_ROUTES: list[dict[str, Any]] = []  # table is canonical data now


def _match(sig: TaskSignal, when: dict[str, Any]) -> bool:
    for k, want in when.items():
        have = getattr(sig, k, None)
        if k == "domains":   # intersect, not equality
            if not set(have or ()) & set(want or ()):
                return False
        elif isinstance(want, list):
            if have not in want:
                return False
        elif have != want:
            return False
    return True


def load_routes(path: str | Path | None = None) -> list[dict[str, Any]]:
    from platformforge.resources import data_path
    if path and Path(path).is_file():
        doc = yaml.safe_load(Path(path).read_text()) or {}
        return doc.get("routes", []) or []
    default = data_path("rules", "catalog", "routing.yaml")
    if default.is_file():
        doc = yaml.safe_load(default.read_text()) or {}
        return doc.get("routes", []) or []
    return BUILTIN_ROUTES


def _specialists_for(domains: list[str]) -> list[str]:
    return [DOMAIN_SPECIALIST[d] for d in domains
            if d in DOMAIN_SPECIALIST]


def _needs_critical(signal: TaskSignal) -> bool:
    """§89 — critical review is mandatory, not optional."""
    return bool(
        (signal.production and signal.mutability == "mutate")
        or signal.destructive
        or (signal.security_sensitive and signal.task_type == "change")
        or (signal.optimization and signal.fleet_scope))


def _needs_debate(signal: TaskSignal) -> bool:
    """§88 — debate opens only on these; never by default."""
    return bool(signal.conflict or signal.comparison
                or (signal.risk in ("high", "critical")
                    and signal.evidence_completeness < 0.5))


def _budget(signal: TaskSignal, mode: str) -> str:
    if mode == "deterministic":
        return "tiny"
    if mode in ("debate", "critical-review") or signal.risk == "critical":
        return "critical" if signal.risk == "critical" else "deep"
    if mode == "coordinated" or signal.fleet_scope:
        return "deep"
    if mode == "multi-specialist" or signal.complexity == "medium":
        return "standard"
    return "small"


def _dag(mode: str, coordinator: str, specialists: list[str],
         reviewers: list[str], verifier: str,
         production: bool) -> list[dict[str, Any]]:
    """Skeleton stage list for the decision — the orchestrator expands
    it into the full loop DAG at prepare() time."""
    if mode == "deterministic":
        return []
    dag: list[dict[str, Any]] = [{"stage": "extract",
                                  "agent": "pf-extractor"}]
    if coordinator:
        dag.insert(0, {"stage": "dispatch", "agent": coordinator})
    dag += [{"stage": f"specialist:{s}", "agent": s}
            for s in specialists]
    dag += [{"stage": f"review:{r}", "agent": r} for r in reviewers]
    if production:
        dag.append({"stage": "approval", "agent": "human-gate",
                    "external": True})
    dag.append({"stage": "verify", "agent": verifier})
    return dag


def route(signal: TaskSignal, routes_path: str | Path | None = None) -> dict[str, Any]:
    """Compute the full dispatch decision (§82)."""
    routes = load_routes(routes_path)
    specialists: list[str] = []
    reviewers: list[str] = []
    coordinator = ""
    reasons: list[str] = []
    fallbacks: list[str] = ["playbook"]

    # --- table rules (data) ------------------------------------------
    for r in routes:
        if _match(signal, r.get("when", {})):
            for a in r.get("agents", []):
                if a not in specialists:
                    specialists.append(a)
            for a in r.get("add_specialists", []):
                if a not in specialists:
                    specialists.append(a)
            for a in r.get("add_reviewers", []):
                if a not in reviewers:
                    reviewers.append(a)
            if r.get("coordinator") and not coordinator:
                coordinator = r["coordinator"]
            if r.get("reason"):
                reasons.append(r["reason"])

    # --- domain-derived specialists ----------------------------------
    for s in _specialists_for(signal.domains):
        if s not in specialists:
            specialists.append(s)

    # --- mode (policy, §83–89) -----------------------------------------
    mode = "deterministic"
    n = len(specialists)
    if _needs_critical(signal):
        mode = "critical-review"
        coordinator = coordinator or "platform-change-coordinator"
        for r in ("platform-operations-safety-reviewer",
                  "platform-security-reviewer"):
            if r not in reviewers:
                reviewers.append(r)
        reasons.append("critical-review mandatory: production/IAM/"
                       "destructive/fleet-optimization (§89)")
    elif _needs_debate(signal):
        mode = "debate"
        reasons.append("debate opened: conflict/comparison/high-risk "
                       "low-confidence (§88)")
    elif signal.fleet_scope or signal.task_type == "fleet":
        mode = "coordinated"
        coordinator = coordinator or "platform-fleet-coordinator"
    elif signal.task_type in ("incident",) or signal.incident_status == "active":
        mode = "coordinated"
        coordinator = coordinator or "platform-incident-coordinator"
    elif signal.complexity == "high" or n >= 3:
        mode = "coordinated"
        coordinator = coordinator or TASK_COORDINATOR.get(
            signal.task_type, "platform-orchestrator")
    elif n == 2:
        mode = "multi-specialist"
    elif n == 1 or (signal.domains and signal.task_type
                    in ("analysis", "review")):
        mode = "single-specialist"

    if signal.task_type == "lint":
        mode = "deterministic"
        specialists, reviewers, coordinator = [], [], ""

    # mandatory reviewers/verifier whenever agents run (§267)
    verifier = ""
    if mode != "deterministic":
        verifier = "platform-verifier"
        if "platform-evidence-reviewer" not in reviewers:
            reviewers.insert(0, "platform-evidence-reviewer")
        if signal.security_sensitive \
                and "platform-security-reviewer" not in reviewers:
            reviewers.append("platform-security-reviewer")
            reasons.append("security-sensitive → security reviewer")

    if mode == "debate":
        reviewers.append("platform-debate-referee")
    if not signal.evidence_available or signal.evidence_completeness < 0.5:
        reasons.append("evidence incomplete — expect named unresolved, "
                       "not guesses")
    if signal.expected_cost == "high" or signal.expected_token_cost == "high":
        reasons.append("high expected cost — deterministic-first "
                       "mandated")
    if signal.freshness in ("stale", "unknown"):
        reasons.append(f"freshness={signal.freshness} — freshness "
                       "evidence required")

    agents = ([coordinator] if coordinator else []) + specialists \
        + reviewers + ([verifier] if verifier else [])
    return {
        "mode": mode,
        "coordinator": coordinator,
        "specialists": specialists,
        "reviewers": reviewers,
        "verifier": verifier,
        "dag": _dag(mode, coordinator, specialists, reviewers, verifier,
                    signal.production),
        "budget": _budget(signal, mode),
        "reasons": reasons or [("deterministic-first: no rule forced "
                                "an agentic mode")],
        "fallbacks": fallbacks,
        "agents": agents,          # §82 compat: flattened dispatch list
        "signal": {k: getattr(signal, k)
                   for k in signal.__dataclass_fields__},
    }


def validate_routing(routes_path: str | Path | None = None) -> dict[str, Any]:
    """§91 — every agent referenced by routing.yaml AND by the
    orchestration loops must resolve; unknown refs are drift, not
    missing features. Also lints delegation edges in the roster."""
    from platformforge.agents.orchestrator import load_loops
    from platformforge.agents.roster import AGENTS, resolve
    problems: list[str] = []
    routes = load_routes(routes_path)
    for i, r in enumerate(routes):
        for key in ("agents", "add_specialists", "add_reviewers",
                    "coordinator"):
            ref = r.get(key)
            refs = [ref] if isinstance(ref, str) else (ref or [])
            for a in refs:
                if isinstance(a, str) and resolve(a) is None:
                    problems.append(
                        f"route[{i}] {r.get('name', '?')} references "
                        f"missing agent {a!r}")
        when = r.get("when", {})
        for f in when:
            if f not in TaskSignal.__dataclass_fields__:
                problems.append(f"route[{i}] {r.get('name', '?')} uses "
                                f"unknown signal {f!r}")
    for lname, loop in load_loops().items():
        for st in loop.get("stages", []):
            a = st.get("agent")
            if a and a != "human-gate" and resolve(a) is None:
                problems.append(f"loop {lname} stage {st.get('id')} "
                                f"references missing agent {a!r}")
    for a in AGENTS.values():
        for ref in tuple(a.delegates_to) + tuple(a.reviewers) + \
                ((a.verifier,) if a.verifier else ()):
            if resolve(ref) is None:
                problems.append(f"{a.name} references missing {ref!r}")
        mode_err = a.role not in ("orchestrator", "planner",
                                  "coordinator", "specialist",
                                  "executor", "reviewer", "critic",
                                  "referee", "verifier", "guardian")
        if mode_err:
            problems.append(f"{a.name} bad role {a.role!r}")
    return {"ok": not problems, "problems": problems,
            "routes": len(routes), "agents": len(AGENTS)}
