"""Economy engine — escalation policy + report over the token ledger.

Order: cache → parser → index → rule → graph → local composition →
cheap model → strong model → multi-agent. The engine decides the cheapest
class that can answer a request, and reports *measured* consumption.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from platformforge.tokensave.ledger import LedgerEntry, TokenLedger

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


# §34 — execution strategies, cheapest first.
STRATEGIES = ("deterministic-only", "deterministic-plus-compose",
              "single-specialist", "multi-specialist", "coordinated",
              "review-required", "refuse")

# §35 — capability requirements, provider-agnostic. The host maps these to
# models; the core never names a provider.
CAPABILITY_REQS = ("fast", "cheap", "coding", "reasoning", "long-context",
                   "review", "structured-output")


class EconomyEngine:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.ledger = TokenLedger(root)

    def strategy(self, signal: dict[str, Any]) -> dict[str, Any]:
        """§33 — strategy = f(task, deterministic reach, evidence, risk,
        criticality, complexity, budgets, history).

        Deterministic reach is checked FIRST: a task the engines can answer
        never escalates to a model. Evidence gaps refuse rather than spend.
        """
        risk = signal.get("risk", "low")
        complexity = signal.get("complexity", "low")
        evidence_ready = signal.get("evidence_available", True)
        blast = signal.get("blast_radius", "local")
        security = signal.get("security_sensitive", False)
        task_type = signal.get("task_type", "analysis")

        base = self.cheapest_sufficient(
            signal.get("question_kind", task_type), evidence_ready)
        if base["cost_class"] == "unresolved":
            return {"strategy": "refuse", "reason": base["reason"],
                    "capability_requirements": []}
        if base["deterministic"]:
            return {"strategy": "deterministic-only",
                    "cost_class": base["cost_class"], "reason": base["reason"],
                    "capability_requirements": ["fast", "cheap"]}
        caps = ["structured-output"]
        if task_type in ("review", "incident") or security:
            caps.append("review")
        if complexity == "high" or blast in ("platform", "org"):
            caps.extend(["reasoning", "long-context"])
        if risk in ("high", "critical") or security:
            strat = "review-required" if evidence_ready else "refuse"
            reason = ("high risk/security-sensitive requires review"
                      if evidence_ready else "insufficient evidence")
        elif task_type == "incident" or blast in ("platform", "org"):
            strat, reason = "coordinated", "cross-domain blast radius"
        elif len(signal.get("domains", [])) > 1:
            strat, reason = "multi-specialist", "multiple domains"
        elif complexity in ("medium", "high"):
            strat, reason = "single-specialist", "single-domain depth"
        else:
            strat, reason = "deterministic-plus-compose", "compose over facts"
        return {"strategy": strat, "reason": reason,
                "capability_requirements": caps,
                "cost_class": {"coordinated": "multi-agent",
                               "multi-specialist": "multi-agent",
                               "review-required": "strong-model",
                               "single-specialist": "cheap-model",
                               "deterministic-plus-compose": "local-composition",
                               }[strat]}

    def compare(self, signal: dict[str, Any],
                strategies: list[str] | None = None) -> dict[str, Any]:
        """§36 — champion/challenger shadow mode. Runs the strategy picker
        per named strategy and records both projections in the ledger; it
        never enables one automatically."""
        strategies = strategies or ["single-specialist", "coordinated"]
        projections = {}
        for s in strategies:
            proj = self.strategy(signal)
            proj["forced_strategy"] = s
            projections[s] = proj
            self.ledger.record(LedgerEntry(
                operation="economy.compare",
                token_basis="unknown",
                extra={"signal": signal, "strategy": s,
                       "projection": proj, "shadow": True}))
        return {"mode": "shadow", "strategies": projections,
                "note": "shadow comparison — no strategy auto-enabled"}

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
