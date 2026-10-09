"""Selective verification (§97–104) — VerificationPlanner.

Impact-based, not test-skipping (§103): select the verification tiers the
change's scope/risk/graph-impact/security require, record selected AND
skipped with reasons in the verification ledger (§104). Risk floors
(§100) cap how low a risky change may verify; security changes always
include the security check (§101); the verification floor cannot be
lowered by budget pressure (§19/§246).
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

SCHEMA = "platformforge/verification-plan/v1"

TIERS = ("V0-static", "V1-contract", "V2-unit", "V3-integration",
         "V4-runtime", "V5-production-evidence")

TIER_ORDER = {t: i for i, t in enumerate(TIERS)}

# §100 — risk floors: the cheapest tier a risk class may stop at.
RISK_FLOORS = {"low": "V0-static", "medium": "V1-contract",
               "high": "V3-integration", "critical": "V4-runtime"}

SEC_CHECK = "security-verification"   # §101 — always present if touched


@dataclass
class VerificationPlan:
    schema: str = SCHEMA
    risk: str = "low"
    security_sensitive: bool = False
    floor: str = "V0-static"
    selected: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    checks: list[str] = field(default_factory=list)
    reasons: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class VerificationPlanner:
    """Select tiers + checks from change signal; write the ledger."""

    def __init__(self, root: str | Path | None = None):
        self.root = Path(root) if root else None

    def plan(self, *, risk: str = "low", security_sensitive: bool = False,
             change_scope: str = "local", impacted_nodes: int = 0,
             touches_security: bool = False,
             runtime_change: bool = False,
             available_checks: list[str] | None = None,
             budget_pressure: bool = False) -> VerificationPlan:
        floor = RISK_FLOORS.get(risk, "V0-static")

        # graph-aware selection (§102): large blast raises the floor
        if impacted_nodes > 100 and TIER_ORDER[floor] < TIER_ORDER[
                "V2-unit"]:
            floor = "V2-unit"
        if change_scope in ("platform", "org") and TIER_ORDER[floor] < \
                TIER_ORDER["V3-integration"]:
            floor = "V3-integration"
        if runtime_change and TIER_ORDER[floor] < TIER_ORDER[
                "V4-runtime"]:
            floor = "V4-runtime"

        # budget may never lower the floor (§246 property)
        selected = TIERS[:TIER_ORDER[floor] + 1]
        skipped = TIERS[TIER_ORDER[floor] + 1:]

        checks: list[str] = []
        reasons: dict[str, str] = {
            "floor": f"risk={risk} → floor {floor}"}
        if touches_security or security_sensitive:
            checks.append(SEC_CHECK)
            reasons[SEC_CHECK] = "§101 — security change always verifies security"
        if budget_pressure:
            reasons["budget"] = ("budget pressure recorded — floor "
                                 "unchanged (verification floor is "
                                 "protected)")

        plan = VerificationPlan(risk=risk,
                                security_sensitive=security_sensitive
                                or touches_security,
                                floor=floor, selected=list(selected),
                                skipped=list(skipped), checks=checks,
                                reasons=reasons)
        self._record(plan)
        return plan

    def _record(self, plan: VerificationPlan) -> None:
        """§104 — verification ledger: selected, skipped, why."""
        if not self.root:
            return
        d = self.root / ".platformforge" / "ledger"
        d.mkdir(parents=True, exist_ok=True)
        row = {"schema": SCHEMA, "ts": time.time(),
               "selected": plan.selected, "skipped": plan.skipped,
               "checks": plan.checks, "reasons": plan.reasons}
        with open(d / "verification.jsonl", "a") as fh:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
