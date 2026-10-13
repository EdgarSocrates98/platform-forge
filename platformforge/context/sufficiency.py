"""Context sufficiency (§65–67) and quality (§69)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


class Sufficiency:
    SUFFICIENT = "sufficient"
    PARTIAL = "partial"
    INSUFFICIENT = "insufficient"     # §67 — never answer with confidence


@dataclass
class ContextSufficiencyResult:
    state: str                       # Sufficiency.*
    missing: list[str] = field(default_factory=list)
    reason: str = ""
    coverage: dict[str, float] = field(default_factory=dict)

    def confident(self) -> bool:
        """§67 — insufficient context forbids confident answers."""
        return self.state == Sufficiency.SUFFICIENT

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def assess(*, required: list[str], present: list[str],
           essential_fit: bool = True) -> ContextSufficiencyResult:
    """Sufficiency = did the needed evidence sections make the pack?

    `essential_fit=False` means the budget could not hold essential
    evidence → insufficient (never silently truncated, §235)."""
    missing = [r for r in required if r not in present]
    if not essential_fit:
        return ContextSufficiencyResult(
            Sufficiency.INSUFFICIENT, missing or ["essential-evidence"],
            "essential evidence does not fit the context budget",
            coverage={"evidence": (len(present) /
                                   max(1, len(present) + len(missing)))})
    if missing:
        return ContextSufficiencyResult(
            Sufficiency.PARTIAL, missing,
            f"missing sections: {missing}",
            coverage={"evidence": len(present) /
                      max(1, len(present) + len(missing))})
    return ContextSufficiencyResult(
        Sufficiency.SUFFICIENT, coverage={"evidence": 1.0})
