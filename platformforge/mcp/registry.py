"""Capability registry — every MCP tool maps 1:1 to a core function the
CLI already calls. Bounds are declared per-tool and enforced on output."""

from __future__ import annotations

import dataclasses as _dc
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Capability:
    """§112 capability registry v2 — declarative contract per tool.

    `handler` resolves the implementation; the rest describes the boundary
    an orchestrator can negotiate against (§139)."""
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: str                       # dotted path resolved lazily
    max_results: int = 100
    max_bytes: int = 32_000
    detail_levels: tuple[str, ...] = ("summary", "normal", "full")
    version: str = "1"
    domain: str = "core"
    output_schema: str = "platformforge/result/v1"
    risk: str = "read"                 # read | simulate | guarded
    offline: bool = True
    mutable: bool = False              # core never mutates external state
    evidence_required: bool = True     # findings need evidence fact_ids
    cost_class: str = "cheap"          # cheap | moderate | expensive
    agent_requirements: tuple[str, ...] = ()

    def contract(self) -> dict[str, Any]:
        """§112 v2 projection — the negotiable capability descriptor."""
        return {"id": self.name, "version": self.version,
                "domain": self.domain, "input_schema": self.input_schema,
                "output_schema": self.output_schema, "risk": self.risk,
                "offline": self.offline, "mutable": self.mutable,
                "evidence_required": self.evidence_required,
                "cost_class": self.cost_class,
                "agent_requirements": list(self.agent_requirements),
                "detail_levels": list(self.detail_levels),
                "bounds": {"max_results": self.max_results,
                           "max_bytes": self.max_bytes}}


# §112 — per-tool v2 metadata (domain / risk / cost / evidence policy).
_V2: dict[str, dict[str, Any]] = {
    "platformforge_inspect": {"domain": "core"},
    "platformforge_analyze": {"domain": "multi", "cost_class": "moderate"},
    "platformforge_judge": {"domain": "rules"},
    "platformforge_graph_query": {"domain": "graph"},
    "platformforge_slo": {"domain": "sre"},
    "platformforge_economy": {"domain": "economy"},
    "platformforge_maturity": {"domain": "product"},
    "platformforge_agents": {"domain": "agents"},
    "platformforge_collect": {"domain": "core", "cost_class": "moderate"},
    "platformforge_diagnose": {"domain": "sre", "cost_class": "moderate"},
    "platformforge_plan": {"domain": "core"},
    "platformforge_risk": {"domain": "core"},
    "platformforge_explain": {"domain": "core"},
    "platformforge_recommend": {"domain": "core"},
    "platformforge_security_scan": {"domain": "security",
                                    "cost_class": "moderate"},
    "platformforge_reliability": {"domain": "sre"},
    "platformforge_drift": {"domain": "iac"},
    "platformforge_change_verify": {"domain": "change", "risk": "simulate",
                                    "cost_class": "expensive"},
    "platformforge_change_review": {"domain": "change", "risk": "simulate",
                                    "cost_class": "expensive"},
    "platformforge_finops": {"domain": "finops", "cost_class": "moderate"},
    "platformforge_observe": {"domain": "sre", "cost_class": "moderate"},
    "platformforge_evals": {"domain": "lab", "cost_class": "moderate"},
    "platformforge_lab_chaos": {"domain": "lab", "risk": "guarded",
                                "mutable": True,
                                "agent_requirements": ("allow_prod",)},
    "platformforge_correlate": {"domain": "sre"},
    "platformforge_policy": {"domain": "rules"},
    "platformforge_integrate": {"domain": "adapters", "risk": "guarded",
                                "mutable": True},
    "platformforge_capability": {"domain": "core"},
}


def _apply_v2(entries: list[Capability]) -> dict[str, Capability]:
    return {c.name: _dc.replace(c, **_V2.get(c.name, {}))
            for c in entries}


CAPABILITIES: dict[str, Capability] = _apply_v2([
    Capability("platformforge_inspect",
               "Inventory analyzable artifacts under a root",
               {"type": "object", "properties": {"repo": {"type": "string"}}},
               "cli:inspect"),
    Capability("platformforge_analyze",
               "Run a domain analyzer (iac|plan|state|k8s|gitops|gha|iam|"
               "sbom|secrets|supply|catalog|crossplane|helm|kustomize|"
               "hubble|kyverno|cosign|slsa|cloud-aws|cloud-azure|cloud-gcp|"
               "ownership|contradictions)",
               {"type": "object", "required": ["domain", "path"],
                "properties": {"domain": {"type": "string"},
                               "path": {"type": "string"}},
                },
               "cli:analyze", max_bytes=64_000),
    Capability("platformforge_judge",
               "Apply the rule catalog to a facts document",
               {"type": "object", "required": ["facts_path"],
                "properties": {"facts_path": {"type": "string"}}},
               "cli:judge"),
    Capability("platformforge_graph_query",
               "Graph query: deps|dependents|blast|paths|gaps|cycles|"
               "identity-become|identity-access|identity-workloads|"
               "identity-blast",
               {"type": "object", "required": ["query"],
                "properties": {"query": {"type": "string"},
                               "node": {"type": "string"},
                               "src": {"type": "string"},
                               "dst": {"type": "string"}}},
               "cli:graph"),
    Capability("platformforge_slo",
               "Compute error budget for an SLO contract",
               {"type": "object", "required": ["contract"],
                "properties": {"contract": {"type": "string"},
                               "sli": {"type": "object"}}},
               "cli:observe_slo"),
    Capability("platformforge_economy",
               "Token/byte economy report",
               {"type": "object", "properties": {}},
               "cli:economy", max_results=50),
    Capability("platformforge_maturity",
               "CNCF platform maturity scoring from declared signals",
               {"type": "object", "required": ["signals"],
                "properties": {"signals": {"type": "object"}}},
               "cli:product_maturity"),
    Capability("platformforge_agents",
               "List the agent roster with contracts",
               {"type": "object", "properties": {}},
               "cli:agents_list"),
    Capability("platformforge_collect",
               "Sniff artifact dumps (k8s/plan/state/iam/sbom/supply/"
               "finops/secrets) under a path → merged facts",
               {"type": "object", "required": ["path"],
                "properties": {"path": {"type": "string"}}},
               "cli:collect", max_bytes=64_000),
    Capability("platformforge_diagnose",
               "Node diagnosis: facts + findings + blast + unresolved",
               {"type": "object", "required": ["node"],
                "properties": {"node": {"type": "string"},
                               "findings": {"type": "string"},
                               "facts": {"type": "string"}}},
               "cli:diagnose"),
    Capability("platformforge_plan",
               "Findings doc → ordered remediation plan (severity→blast)",
               {"type": "object", "required": ["findings_path"],
                "properties": {"findings_path": {"type": "string"},
                               "facts_path": {"type": "string"}}},
               "cli:plan"),
    Capability("platformforge_risk",
               "Decomposed change risk for a node or explicit signals",
               {"type": "object",
                "properties": {"node": {"type": "string"},
                               "signals": {"type": "object"}}},
               "cli:risk"),
    Capability("platformforge_explain",
               "Evidence chain for a finding_id or rule_id",
               {"type": "object", "required": ["findings_path", "name"],
                "properties": {"findings_path": {"type": "string"},
                               "name": {"type": "string"},
                               "facts_path": {"type": "string"}}},
               "cli:explain"),
    Capability("platformforge_recommend",
               "Findings → Recommendation objects (no-evidence → refused)",
               {"type": "object", "required": ["findings_path"],
                "properties": {"findings_path": {"type": "string"}}},
               "cli:recommend"),
    Capability("platformforge_security_scan",
               "Secrets + IAM + SBOM + supply bundle → security findings",
               {"type": "object", "required": ["path"],
                "properties": {"path": {"type": "string"}}},
               "cli:security", max_bytes=64_000),
    Capability("platformforge_reliability",
               "SRE+K8S rule subset over a facts doc",
               {"type": "object", "required": ["facts_path"],
                "properties": {"facts_path": {"type": "string"}}},
               "cli:reliability"),
    Capability("platformforge_drift",
               "IaC drift: desired HCL dir vs observed state JSON",
               {"type": "object", "required": ["config", "state"],
                "properties": {"config": {"type": "string"},
                               "state": {"type": "string"}}},
               "cli:drift"),
    Capability("platformforge_change_verify",
               "Sandboxed change review: copy → apply patch/files → "
               "analyze before/after → delta + risk",
               {"type": "object", "required": ["root"],
                "properties": {"root": {"type": "string"},
                               "patch": {"type": "string"},
                               "files": {"type": "object"}}},
               "cli:change_verify", max_bytes=64_000),
    Capability("platformforge_change_review",
               "§104 full change review over the sandbox delta: diff → "
               "planned graph → blast → findings delta → risk → validation",
               {"type": "object", "required": ["root"],
                "properties": {"root": {"type": "string"},
                               "patch": {"type": "string"},
                               "files": {"type": "object"},
                               "signals": {"type": "object"}}},
               "cli:change_review", max_bytes=64_000),
    Capability("platformforge_finops",
               "FinOps ops: costs|allocate|focus|focus-validate|unit "
               "(unit needs measured denominators)",
               {"type": "object", "required": ["path"],
                "properties": {"op": {"type": "string"},
                               "path": {"type": "string"},
                               "by": {"type": "string"},
                               "denominators": {"type": "object"}}},
               "cli:finops"),
    Capability("platformforge_observe",
               "Observe ops: slo|slo-burn|otel|semconv|timeline|postmortem|"
               "dr|prometheus|grafana|incident|capacity",
               {"type": "object", "required": ["op"],
                "properties": {"op": {"type": "string"},
                               "path": {"type": "string"},
                               "contract": {"type": "string"},
                               "sli": {"type": "object"},
                               "windows": {"type": "object"},
                               "alerts": {"type": "string"},
                               "changes": {"type": "string"},
                               "incident": {"type": "string"},
                               "facts": {"type": "string"},
                               "window": {"type": "integer"}}},
               "cli:observe", max_bytes=64_000),
    Capability("platformforge_evals",
               "Run the eval corpus (evals/cases/*/case.yaml)",
               {"type": "object",
                "properties": {"cases": {"type": "string"},
                               "type": {"type": "string"}}},
               "cli:evals"),
    Capability("platformforge_lab_chaos",
               "Graph-simulated fault injection (§93); prod refused unless "
               "allow_prod",
               {"type": "object", "required": ["scenario"],
                "properties": {"scenario": {"type": "string"},
                               "allow_prod": {"type": "boolean"}}},
               "cli:lab_chaos"),
    Capability("platformforge_correlate",
               "OTel/telemetry correlation (observe otel)",
               {"type": "object", "required": ["path"],
                "properties": {"path": {"type": "string"}}},
               "cli:correlate"),
    Capability("platformforge_policy",
               "Rule catalog as policy layer (check|list)",
               {"type": "object", "required": ["op"],
                "properties": {"op": {"type": "string"},
                               "facts_path": {"type": "string"}}},
               "cli:policy"),
    Capability("platformforge_integrate",
               "Host parity files (mcp integrate/detach)",
               {"type": "object", "required": ["host"],
                "properties": {"host": {"type": "string"},
                               "detach": {"type": "boolean"}}},
               "cli:integrate"),
    Capability("platformforge_capability",
               "Capability list/describe/manifest",
               {"type": "object",
                "properties": {"op": {"type": "string"},
                               "name": {"type": "string"}}},
               "cli:capability"),
])


def tool_descriptors() -> list[dict[str, Any]]:
    """MCP tools/list payload."""
    return [{
        "name": c.name,
        "description": c.description,
        "inputSchema": c.input_schema,
        "annotations": {"readOnlyHint": True, "destructiveHint": False},
        "x-bounds": {"max_results": c.max_results,
                     "max_bytes": c.max_bytes,
                     "detail_levels": list(c.detail_levels)},
    } for c in CAPABILITIES.values()]
