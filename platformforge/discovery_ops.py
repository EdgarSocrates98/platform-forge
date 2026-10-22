# platformforge/discovery_ops.py
"""§6.2 conceptual-op map -> real ``platformforge`` verbs (lf-0037).

Single source for the ``forge/context/v1`` manifest ``discovery.ops`` /
``discovery.commands`` and the ``platformforge capabilities`` verb.
"""

from __future__ import annotations

from typing import Any

CLI = "platformforge"

DOMAINS: tuple[str, ...] = (
    "platform-engineering",
    "infrastructure-as-code",
    "kubernetes",
    "crossplane",
    "terraform",
    "finops",
    "sre",
    "supply-chain",
)

DOMAIN_PREFIXES: dict[str, tuple[str, ...]] = {
    "platform-engineering": ("platform", "gitops", "idp"),
    "infrastructure-as-code": ("iac", "terraform", "crossplane", "bicep", "pulumi"),
    "kubernetes": ("kube", "k8s"),
    "crossplane": ("crossplane",),
    "terraform": ("tf", "terraform"),
    "finops": ("finops", "cost", "costs"),
    "sre": ("sre", "observe", "otel", "incident", "reliab"),
    "supply-chain": ("supply", "sbom", "secrets", "sec", "iam", "policy"),
}


def domain_prefixes(domain: str) -> tuple[str, ...]:
    norm = domain.strip().lower().replace("_", "-")
    return DOMAIN_PREFIXES.get(norm, (norm,))


PROTOCOLS: tuple[dict[str, str], ...] = (
    {"id": "forge/v1", "version": "1"},
    {"id": "forge/context/v1", "version": "1"},
    {"id": "forge/context-registry/v1", "version": "1"},
)

MCP_INTERFACE: dict[str, Any] = {
    "server_name": "platformforge",
    "command": [CLI, "mcp", "serve"],
    "verify_tool": "pf_status",
}

OPS: dict[str, dict[str, Any]] = {
    "capabilities.list": {
        "id": "capabilities",
        "argv": ["capabilities"],
        "mode": "direct-capability",
        "description": "installed capabilities, protocols and the §6.2 op map",
    },
    "protocol.describe": {
        "id": "capabilities",
        "argv": ["capabilities"],
        "mode": "direct-capability",
        "description": "protocols + interfaces section of `capabilities`",
    },
    "rules.search": {
        "id": "rules-search",
        "argv": [
            "policy", "search", "--query", "{term}", "--domain", "{domain}",
            "--severity", "{severity}", "--limit", "{limit}", "--cursor", "{cursor}",
        ],
        "mode": "direct-capability",
        "description": "keyword/domain/severity filter over the policy rule catalog, paginated",
    },
    "rules.get": {
        "id": "rules-get",
        "argv": ["policy", "get", "{rule_id}"],
        "mode": "direct-capability",
        "description": "one rule's full policy entry by id",
    },
    "knowledge.search": {
        "id": "knowledge-search",
        "argv": [
            "knowledge", "search", "{term}", "--domain", "{domain}",
            "--limit", "{limit}", "--cursor", "{cursor}",
        ],
        "mode": "direct-capability",
        "description": "offline text search over knowledge packs, one hit per doc",
    },
    "knowledge.get": {
        "id": "knowledge-get",
        "argv": ["knowledge", "get", "{file}"],
        "mode": "direct-capability",
        "description": "resolve one document's absolute path + sha256 + provenance",
    },
    "context.build": {
        "id": "context-pack",
        "argv": ["context", "pack", "--domain", "{domain}"],
        "mode": "direct-capability",
        "description": "bounded domain context pack: rules + knowledge metadata + hash",
    },
    "health.check": {
        "id": "doctor",
        "argv": ["doctor"],
        "mode": "diagnostic-only",
        "description": "environment + installation health",
    },
}


def commands() -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for entry in OPS.values():
        if entry["id"] in seen:
            continue
        seen.add(entry["id"])
        out.append(
            {
                "id": entry["id"],
                "argv": [CLI, *entry["argv"]],
                "mode": entry["mode"],
                "read_only": True,
                "description": entry["description"],
            }
        )
    return out


def ops() -> dict[str, str]:
    return {op: entry["id"] for op, entry in OPS.items()}


def ops_expanded() -> dict[str, dict[str, Any]]:
    return {
        op: {"command": entry["id"], "argv": [CLI, *entry["argv"]]}
        for op, entry in OPS.items()
    }
