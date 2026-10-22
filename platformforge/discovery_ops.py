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


# ---------------------------------------------------------------------------
# §7.2 (install-2.0 ciclo 5, lf-0038) — ops de evals/verification.
#
# `DISCOVERY_OPS` do `_forgecontext.py` canonico e um vocabulario FECHADO com
# os oito ops do §6.2 — `evals.*`/`verification.*` nao podem entrar em
# `discovery.ops` sem alterar o modulo vendored de outra forja (the-forge e
# o dono). Os seis ops viram `discovery.commands` nomeados (hifen: o
# ITEM_ID_RE nao aceita ponto) e `capabilities.evals.ops`.
#
# `evals.result` nao e read_only na intencao (recomputa e ancora o
# scorecard), embora nao escreva; `verification.plan/run` sao os verbos reais
# do ciclo `change propose -> verify` (read-only, evidence explicita).
# ---------------------------------------------------------------------------

EVAL_OPS: dict[str, dict[str, Any]] = {
    "evals.list": {
        "id": "evals-list",
        "argv": ["evals", "list", "--classified"],
        "mode": "direct-capability",
        "read_only": True,
        "description": (
            "evals.list (§7.2) — inventario classificado das suites nas 4 "
            "categorias do §7.1 (developer, runtime-decision, "
            "output-verification, host-conformance)"
        ),
    },
    "evals.describe": {
        "id": "evals-describe",
        "argv": ["evals", "describe", "--suite", "{suite}"],
        "mode": "direct-capability",
        "read_only": True,
        "description": (
            "evals.describe (§7.2) — metadados da suite: categoria, ambiente, "
            "selagem §7.3 e sha256 de integridade; gabarito selado nunca sai"
        ),
    },
    "evals.run": {
        "id": "evals-run",
        "argv": ["evals", "run", "--suite", "{suite}"],
        "mode": "direct-capability",
        "read_only": True,
        "description": (
            "evals.run (§7.2) — executa o runner deterministico da suite; "
            "unresolved nunca e promovido a pass"
        ),
    },
    "evals.result": {
        "id": "evals-result",
        "argv": ["evals", "result", "--suite", "{suite}", "--run", "{run}"],
        "mode": "direct-capability",
        "read_only": True,
        "description": (
            "evals.result (§7.2) — scorecard do corpus (holdout/golden) "
            "ancorado em corpus_hash; demais suites emitem resultado no run"
        ),
    },
    "verification.plan": {
        "id": "verification-plan",
        "argv": ["change", "propose", "--patch", "{patch}"],
        "mode": "direct-capability",
        "read_only": False,
        "description": (
            "verification.plan (§7.2/§7.4) — proposta de mudanca com o plano "
            "de verificacao do sandbox (evidencias esperadas)"
        ),
    },
    "verification.run": {
        "id": "verification-run",
        "argv": ["change", "verify", "--patch", "{patch}"],
        "mode": "direct-capability",
        "read_only": True,
        "description": (
            "verification.run (§7.2/§7.4) — verificacao read-only do delta "
            "do sandbox; falhas e unresolved explicitos; approve/apply "
            "permanecem boundary de host"
        ),
    },
}


def eval_commands() -> list[dict[str, Any]]:
    """Os `discovery.commands` do §7.2 — ids com hifen (o ITEM_ID_RE nao
    aceita ponto); o nome conceitual fica na descricao."""
    return [
        {
            "id": entry["id"],
            "argv": [CLI, *entry["argv"]],
            "mode": entry["mode"],
            "read_only": entry["read_only"],
            "description": entry["description"],
        }
        for entry in EVAL_OPS.values()
    ]


def eval_ops_expanded() -> dict[str, dict[str, Any]]:
    """O mapa §7.2 materializado para `capabilities.evals.ops`."""
    return {
        op: {
            "command": entry["id"],
            "argv": [CLI, *entry["argv"]],
            "read_only": entry["read_only"],
        }
        for op, entry in EVAL_OPS.items()
    }
