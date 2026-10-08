"""Capability manifest — what this forge can do, for sibling forges and
orchestrators. Generated from the code, never hand-maintained."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from platformforge.graph.vocab import EDGE_KINDS, NODE_KINDS
from platformforge.mcp.registry import CAPABILITIES
from platformforge.resources import data_path
from platformforge.rules import load_catalog

_REPO = data_path()


def capability_manifest(repo: str | Path | None = None) -> dict[str, Any]:
    root = Path(repo) if repo else _REPO
    rules = load_catalog(root / "rules" / "catalog")
    try:
        head = subprocess.run(["git", "-C", str(root), "rev-parse", "--short",
                               "HEAD"], capture_output=True, text=True,
                              check=False).stdout.strip()
    except OSError:
        head = "unknown"
    return {
        "manifest": "platformforge/capability-manifest/v2",
        "forge": "platform-forge",
        "version": "0.1.0",
        "commit": head,
        "modes": {"offline": True, "read_only": True,
                  "cloud_mutation": False},
        # §138 — interop fields a sibling forge can negotiate against
        "quality_level": "self-eval",   # no external audit claimed
        "maturity": "beta",
        "required_evidence": {"findings": "evidence_fact_ids non-empty",
                              "tiers": "0-5 only — T6/T7 cannot be facts"},
        "cost_characteristics": {
            c.name: c.cost_class for c in CAPABILITIES.values()},
        "risk": {c.name: c.risk for c in CAPABILITIES.values()},
        "domains": sorted({r.domain for r in rules if r.domain} |
                          {"iac", "k8s", "gitops", "cicd", "sre", "finops",
                           "security", "product", "graph", "live"}),
        "supported_versions": _supported_versions(),
        "tools": sorted(CAPABILITIES),
        "capabilities_v2": [c.contract() for c in CAPABILITIES.values()],
        "rule_count": len(rules),
        "rules": sorted(r.rule_id for r in rules),
        "graph_vocab": {"node_kinds": sorted(NODE_KINDS),
                        "edge_kinds": sorted(EDGE_KINDS)},
        "evidence_tiers": 8,
        "contracts": sorted(p.stem.replace(".schema", "")
                            for p in (root / "contracts").glob("*.schema.json")),
    }


def _supported_versions() -> dict[str, str]:
    """§139/§144 — versions the knowledge registry has evidence for.
    Absence of a product here means 'unresolved', not 'unsupported'."""
    try:
        from platformforge.knowledge.registry import SourceRegistry
        reg = SourceRegistry.default()
    except (OSError, ValueError):
        return {}
    out: dict[str, str] = {}
    for e in reg.entries.values():
        if e.product and e.version:
            out.setdefault(e.product, e.version)
    return dict(sorted(out.items()))
