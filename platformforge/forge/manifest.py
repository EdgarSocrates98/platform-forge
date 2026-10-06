"""Capability manifest — what this forge can do, for sibling forges and
orchestrators. Generated from the code, never hand-maintained."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from platformforge.graph.vocab import EDGE_KINDS, NODE_KINDS
from platformforge.mcp.registry import CAPABILITIES
from platformforge.rules import load_catalog

_REPO = Path(__file__).resolve().parents[2]


def capability_manifest(repo: str | Path | None = None) -> dict[str, Any]:
    root = Path(repo) if repo else _REPO
    rules = load_catalog(root / "rules" / "catalog")
    try:
        head = subprocess.run(["git", "-C", str(root), "rev-parse", "--short",
                               "HEAD"], capture_output=True, text=True
                              ).stdout.strip()
    except Exception:
        head = "unknown"
    return {
        "manifest": "platformforge/capability-manifest/v1",
        "forge": "platform-forge",
        "version": "0.1.0",
        "commit": head,
        "modes": {"offline": True, "read_only": True,
                  "cloud_mutation": False},
        "domains": sorted({r.domain for r in rules if r.domain} |
                          {"iac", "k8s", "gitops", "cicd", "sre", "finops",
                           "security", "product", "graph"}),
        "tools": sorted(CAPABILITIES),
        "rule_count": len(rules),
        "rules": sorted(r.rule_id for r in rules),
        "graph_vocab": {"node_kinds": sorted(NODE_KINDS),
                        "edge_kinds": sorted(EDGE_KINDS)},
        "evidence_tiers": 8,
        "contracts": sorted(p.stem.replace(".schema", "")
                            for p in (root / "contracts").glob("*.schema.json")),
    }
