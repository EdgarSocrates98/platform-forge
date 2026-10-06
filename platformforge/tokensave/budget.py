"""Token budgets — insufficient budget is a named verdict, never silent
evidence sacrifice."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Budget:
    input_budget: int | None = None
    output_budget: int | None = None
    reasoning_budget: int | None = None
    tool_budget: int | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Budget":
        return cls(**{k: d.get(k) for k in cls.__dataclass_fields__})

    def to_dict(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


class BudgetVerdict:
    def __init__(self, decision: str, detail: str = "", reduced_scope=None):
        self.decision = decision  # ok | refuse | reduce_scope | escalate
        self.detail = detail
        self.reduced_scope = reduced_scope

    def to_dict(self) -> dict[str, Any]:
        return {"decision": self.decision, "detail": self.detail,
                "reduced_scope": self.reduced_scope}


def check_input_budget(budget: Budget, estimated_tokens: int,
                       min_essential: int = 0) -> BudgetVerdict:
    """min_essential = tokens needed for essential evidence — below that, refuse
    rather than silently drop evidence."""
    if budget.input_budget is None:
        return BudgetVerdict("ok")
    if estimated_tokens <= budget.input_budget:
        return BudgetVerdict("ok")
    if min_essential and budget.input_budget >= min_essential:
        return BudgetVerdict("reduce_scope",
                             f"budget {budget.input_budget} < needed {estimated_tokens}; "
                             f"keeping essential evidence ({min_essential})")
    return BudgetVerdict("refuse",
                         f"budget {budget.input_budget} < needed {estimated_tokens}; "
                         "refusing rather than dropping essential evidence — "
                         "raise budget or narrow scope",
                         reduced_scope="platform.context.budget.unresolved")
