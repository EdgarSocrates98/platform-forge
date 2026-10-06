"""Native SDD — spec-driven development lifecycle with hash cascade + gates.

No runtime dependency on AgentSpec/cc-sdd/Cavekit — this is first-party.
"""

from platformforge.sdd.lifecycle import (GATE_FAILURES, PHASES, SDDProject,
                                         SddArtifact)

__all__ = ["SDDProject", "SddArtifact", "PHASES", "GATE_FAILURES"]
