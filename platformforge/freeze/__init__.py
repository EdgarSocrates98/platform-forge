"""Freeze governance (prompt_evo_freezing §4–6).

Manifest is *generated* from live registries (contracts dir, capability
registry, CLI parser, MCP tools, agent roster) — never hand-maintained.
"""

from platformforge.freeze.exceptions import FeatureException, exception_errors
from platformforge.freeze.manifest import build_manifest
from platformforge.freeze.snapshots import (
    build_snapshots,
    check_snapshots,
    write_snapshots,
)

__all__ = [
    "FeatureException",
    "build_manifest",
    "build_snapshots",
    "check_snapshots",
    "exception_errors",
    "write_snapshots",
]
