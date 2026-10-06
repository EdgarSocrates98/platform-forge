"""Controlled vocabularies for the platform graph (GRAPHFY.md)."""

NODE_KINDS = frozenset(
    ["repository", "component", "service", "api", "pipeline", "workflow", "artifact", "container_image", "sbom", "team", "owner", "cloud_account", "subscription", "project", "organization", "region", "zone", "vpc_vnet", "subnet", "route", "gateway", "nat", "load_balancer", "dns", "certificate", "cluster", "node_pool", "node", "namespace", "workload", "pod", "k8s_service", "ingress", "iam_principal", "role", "policy", "service_account", "workload_identity", "secret", "database", "cache", "queue", "topic", "bucket", "volume", "terraform_module", "terraform_resource", "crossplane_xr", "argocd_application", "fluxcd_resource", "monitor", "dashboard", "alert", "slo", "cost_center", "budget", "billing_unit", "security_policy", "admission_policy"])

EDGE_KINDS = frozenset(
    ["owns", "depends_on", "deploys_to", "runs_on", "contained_by", "routes_to", "calls", "publishes_to", "consumes", "reads", "writes", "assumes", "impersonates", "can_access", "uses_secret", "exposes", "secured_by", "observed_by", "alerted_by", "governed_by", "provisioned_by", "generated_by", "billed_to", "replicated_to", "fails_over_to"])

PROVENANCES = frozenset({"observed", "declared", "inferred"})

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
    "owns": "unknown", "observed_by": "unknown", "provisioned_by": "unknown",
    "generated_by": "unknown",
}


def impact_of(edge_kind: str) -> str:
    return EDGE_IMPACT.get(edge_kind, "unknown")
