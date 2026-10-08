"""§4 — FREEZE-MANIFEST generated from live registries. Every entry is
computed, so the manifest can't silently drift from the code."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA = "platformforge/freeze-manifest/v1"
CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"


def _cli_verbs() -> list[str]:
    from platformforge.cli.main import build_parser
    p = build_parser()
    sub = next(a for a in p._actions if hasattr(a, "choices") and a.choices)
    return sorted(sub.choices)


def _mcp_tools() -> list[str]:
    from platformforge.mcp.registry import tool_descriptors
    return sorted(t["name"] for t in tool_descriptors())


def _capabilities() -> dict[str, Any]:
    from platformforge.mcp.registry import CAPABILITIES
    contracts = [c.contract() for c in CAPABILITIES.values()]
    return {"count": len(contracts),
            "ids": sorted(c.get("name", c.get("id", "?")) for c in contracts)}


def _schemas() -> dict[str, Any]:
    files = sorted(p.name for p in CONTRACTS.glob("*.schema.json"))
    return {"count": len(files), "files": files}


def _agents() -> dict[str, Any]:
    from platformforge.agents.roster import AGENTS
    by_role: dict[str, int] = {}
    for a in AGENTS.values():
        by_role[a.role] = by_role.get(a.role, 0) + 1
    return {"count": len(AGENTS), "by_role": by_role,
            "names": sorted(AGENTS)}


def _knowledge_packs() -> dict[str, Any]:
    kroot = Path(__file__).resolve().parents[2] / "knowledge"
    packs = sorted(p.name for p in kroot.iterdir() if p.is_dir())
    srcs = 0
    import yaml
    sf = kroot / "sources.yaml"
    if sf.exists():
        srcs = len(yaml.safe_load(sf.read_text()) or {})
    return {"packs": packs, "sources": srcs}


STABILITY = {
    # §4 — honest stability labels, not aspirational ones
    "stable": [
        "fact/finding/graph contracts", "judge rule engine",
        "graphfy query surface", "change sandbox review",
        "tokensave/economy", "lab + evals harness", "MCP server",
    ],
    "experimental": [
        "agentic runtime (router v2, coordinators, debate)",
        "fleet analytics + optimization engine", "federation export",
        "ai platform awareness", "connected live collectors",
    ],
    "internal": [
        "sdd lifecycle machinery", "forge interop envelope",
        "freeze governance (this module)",
    ],
}

KNOWN_GAPS = [
    "agent benchmarks are router projections, not measured model spends",
    "analytics store is single-node SQLite (no concurrent writers)",
    "graph scale beyond 10k nodes / 500k edges is unsupported-on-host here",
    "no production evidence — nothing is production-validated",
    "connected (AWS/k8s) validation requires host credentials — offline by default",
]

PRODUCTION_UNVALIDATED = [
    "every capability — no production telemetry exists in this repo",
]


def build_manifest() -> dict[str, Any]:
    import platform
    import subprocess
    sha = subprocess.run(["git", "rev-parse", "HEAD"], check=False,
                         capture_output=True, text=True).stdout.strip()
    return {
        "schema": SCHEMA,
        "freeze_start_sha": sha,
        "python": platform.python_version(),
        "lifecycle": ["open-development", "freeze-candidate",
                      "architecture-frozen", "dogfooding",
                      "release-candidate", "stable"],
        "lifecycle_state": "dogfooding",
        "public_schemas": _schemas(),
        "cli_surfaces": _cli_verbs(),
        "mcp_surfaces": _mcp_tools(),
        "capabilities": _capabilities(),
        "agent_contracts": _agents(),
        "knowledge_packs": _knowledge_packs(),
        "stability": STABILITY,
        "known_gaps": KNOWN_GAPS,
        "production_unvalidated_claims": PRODUCTION_UNVALIDATED,
        "supported_runtimes": ["python 3.10", "python 3.11",
                               "python 3.12", "python 3.13"],
    }


def render_markdown(m: dict[str, Any]) -> str:
    a = m["agent_contracts"]
    lines = [
        "# FREEZE-MANIFEST",
        "",
        "Generated from live registries — `platformforge freeze manifest`.",
        "",
        f"- freeze_start_sha: `{m['freeze_start_sha']}`",
        (f"- lifecycle state: **{m['lifecycle_state']}** "
         f"({' → '.join(m['lifecycle'])})"),
        (f"- python: {m['python']} (supported: "
         f"{', '.join(m['supported_runtimes'])})"),
        "",
        "## Surfaces",
        "",
        (f"- public schemas: {m['public_schemas']['count']} "
         f"(contracts/*.schema.json)"),
        (f"- CLI verbs: {len(m['cli_surfaces'])} — "
         f"{', '.join(m['cli_surfaces'])}"),
        f"- MCP tools: {len(m['mcp_surfaces'])}",
        f"- capabilities: {m['capabilities']['count']}",
        (f"- agents: {a['count']} "
         f"({', '.join(f'{r}:{n}' for r, n in sorted(a['by_role'].items()))})"),
        (f"- knowledge packs: {', '.join(m['knowledge_packs']['packs'])} "
         f"({m['knowledge_packs']['sources']} registered sources)"),
        "",
        "## Stability labels",
        "",
    ]
    for k, v in m["stability"].items():
        lines += [f"**{k}**", ""] + [f"- {x}" for x in v] + [""]
    lines += ["## Known gaps", ""]
    lines += [f"- {x}" for x in m["known_gaps"]]
    lines += ["", "## Production-unvalidated claims", ""]
    lines += [f"- {x}" for x in m["production_unvalidated_claims"]]
    return "\n".join(lines) + "\n"


def write_manifest(path: str | Path) -> dict[str, Any]:
    m = build_manifest()
    Path(path).write_text(render_markdown(m))
    return m


if __name__ == "__main__":  # pragma: no cover
    print(json.dumps(build_manifest(), indent=2, sort_keys=True))
