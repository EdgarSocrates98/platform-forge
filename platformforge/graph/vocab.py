"""Controlled vocabularies for the platform graph (GRAPHFY.md)."""

NODE_KINDS = frozenset(
    ["repository", "component", "service", "api", "pipeline", "workflow", "artifact", "container_image", "sbom", "team", "owner", "cloud_account", "subscription", "project", "organization", "region", "zone", "vpc_vnet", "subnet", "route", "gateway", "nat", "load_balancer", "dns", "certificate", "cluster", "node_pool", "node", "namespace", "workload", "pod", "k8s_service", "ingress", "iam_principal", "role", "policy", "service_account", "workload_identity", "secret", "database", "cache", "queue", "topic", "bucket", "volume", "terraform_module", "terraform_resource", "crossplane_xr", "crossplane_xrd", "crossplane_composition", "crossplane_managed_resource", "crossplane_provider", "argocd_application", "fluxcd_resource", "monitor", "dashboard", "alert", "slo", "cost_center", "budget", "billing_unit", "security_policy", "admission_policy", "helm_chart", "autoscaler", "storage", "flow",
     # cycle4 — operational layer (execution events, not dependencies)
     "operation", "change_intent", "change_plan", "execution_envelope",
     "approval", "runbook", "platform_request", "policy_decision",
     "rollback",
     # cycle5 — organizational layer (§18) + AI platform (§190)
     "business_unit", "platform", "platform_capability", "domain",
     "product", "environment", "fleet", "operation_class",
     "golden_path", "cost_unit",
     "accelerator", "gpu_pool", "model", "model_endpoint",
     "inference_service", "training_job", "vector_store"])

EDGE_KINDS = frozenset(
    ["owns", "depends_on", "deploys_to", "runs_on", "contained_by", "routes_to", "calls", "publishes_to", "consumes", "reads", "writes", "assumes", "impersonates", "can_access", "uses_secret", "exposes", "secured_by", "observed_by", "alerted_by", "governed_by", "provisioned_by", "generated_by", "billed_to", "replicated_to", "fails_over_to", "scales", "attached_to",
     # cycle4 — operational edges (provenance observed, layer=operation)
     "intends", "planned_by", "mutates", "approved_by", "executed_by",
     "verifies", "rolled_back_by", "requested_by", "produced_receipt",
     # cycle5 — organizational edges (§19)
     "provides", "operates", "supports", "funded_by", "uses_capability",
     "uses_golden_path", "escapes_golden_path", "affected_by",
     "shares_runtime_with"])

PROVENANCES = frozenset({"observed", "planned", "declared", "inferred"})

# Edge kind → impact class for blast-radius decomposition. Proximity is not
# causality: classes are reported separately, never merged into one number.
EDGE_IMPACT = {
    "calls": "runtime", "routes_to": "runtime", "consumes": "runtime",
    "publishes_to": "runtime", "reads": "runtime", "writes": "runtime",
    "depends_on": "reliability", "runs_on": "reliability",
    "contained_by": "reliability", "replicated_to": "reliability",
    "fails_over_to": "reliability", "deploys_to": "reliability",
    "secured_by": "security", "can_access": "security",
    "uses_secret": "security", "assumes": "security",
    "impersonates": "security", "exposes": "security",
    "governed_by": "compliance", "alerted_by": "compliance",
    "billed_to": "cost",
    "scales": "capacity", "attached_to": "network",
    "owns": "unknown", "observed_by": "unknown", "provisioned_by": "unknown",
    "generated_by": "unknown",
    # cycle4 — operational edges get their own impact class so blast
    # radius never conflates execution history with dependencies
    "intends": "operation", "planned_by": "operation",
    "mutates": "operation", "approved_by": "operation",
    "executed_by": "operation", "verifies": "operation",
    "rolled_back_by": "operation", "requested_by": "operation",
    "produced_receipt": "operation",
    # cycle5 — organizational edges: reported under their own class so
    # org-structure blast never merges with technical dependencies
    "owns": "organizational", "provides": "organizational",
    "operates": "organizational", "supports": "organizational",
    "funded_by": "cost", "uses_capability": "organizational",
    "uses_golden_path": "organizational",
    "escapes_golden_path": "organizational",
    "affected_by": "reliability", "shares_runtime_with": "reliability",
}


def impact_of(edge_kind: str) -> str:
    return EDGE_IMPACT.get(edge_kind, "unknown")
