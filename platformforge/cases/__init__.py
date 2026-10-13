"""Real-world case corpus + deterministic replay (§52–§68).

A case is `.platformforge/cases/<tier>/<id>/case.yaml` plus artifacts.
Replay reuses the lab analyzer machinery: fixture → facts → RuleEngine
→ compare against `expected_known_truth`. No new platform subsystem —
a corpus format and a grading harness over existing verbs.
"""

from platformforge.cases.casefile import CaseFile, case_errors, load_case
from platformforge.cases.replay import replay_all, replay_case

__all__ = ["CaseFile", "case_errors", "load_case",
           "replay_all", "replay_case"]
