"""Economy engine — escalation policy + report over the token ledger.

Order: cache → parser → index → rule → graph → local composition →
cheap model → strong model → multi-agent. The engine decides the cheapest
class that can answer a request, and reports *measured* consumption.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from platformforge.tokensave.ledger import TokenLedger

COST_ORDER = [
    "cache", "parser", "index", "rule", "graph", "local-composition",
    "cheap-model", "strong-model", "multi-agent",
]
DETERMINISTIC_CLASSES = {"cache", "parser", "index", "rule", "graph",
                         "local-composition"}


@dataclass
class CostClass:
    name: str
    deterministic: bool
    needs_model: bool


class EconomyEngine:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.ledger = TokenLedger(root)

    def cheapest_sufficient(self, question_kind: str,
                            evidence_ready: bool = True) -> dict[str, Any]:
        """Which cost class can answer? Deterministic wherever possible."""
        deterministic_answers = {
            "lint", "rule-check", "inventory", "diff", "drift", "graph-query",
            "impact", "policy", "budget-check", "freshness", "scorecard",
            "slo-calc", "redaction", "compaction", "routing",
        }
        if question_kind in deterministic_answers:
            cls = {"lint": "rule", "rule-check": "rule", "inventory": "index",
                   "diff": "parser", "drift": "graph", "graph-query": "graph",
                   "impact": "graph", "policy": "rule", "budget-check": "cache",
                   "freshness": "index", "scorecard": "local-composition",
                   "slo-calc": "rule", "redaction": "parser",
                   "compaction": "parser", "routing": "rule"}[question_kind]
            return {"cost_class": cls, "deterministic": True,
                    "reason": "answerable without a model"}
        if not evidence_ready:
            return {"cost_class": "unresolved", "deterministic": False,
                    "reason": "insufficient evidence — refuse, don't spend a model"}
        return {"cost_class": "cheap-model", "deterministic": False,
                "reason": "requires composition beyond deterministic reach"}

    def report(self) -> dict[str, Any]:
        return {"cost_order": COST_ORDER, "ledger": self.ledger.report()}
