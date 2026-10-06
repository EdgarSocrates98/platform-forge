"""Capability registry — every MCP tool maps 1:1 to a core function the
CLI already calls. Bounds are declared per-tool and enforced on output."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class Capability:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: str                       # dotted path resolved lazily
    max_results: int = 100
    max_bytes: int = 32_000
    detail_levels: tuple[str, ...] = ("summary", "normal", "full")


CAPABILITIES: dict[str, Capability] = {c.name: c for c in [
    Capability("platformforge_inspect",
               "Inventory analyzable artifacts under a root",
               {"type": "object", "properties": {"repo": {"type": "string"}}},
               "cli:inspect"),
    Capability("platformforge_analyze",
               "Run a domain analyzer (iac|plan|state|k8s|gitops|gha|iam|"
               "sbom|secrets|supply|catalog|crossplane)",
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
               "Graph query: deps|dependents|blast|paths|gaps|cycles",
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
]}


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
