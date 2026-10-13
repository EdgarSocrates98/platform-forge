"""Routing control plane contracts (§138–160): RoutingRequest,
RoutingDecision, profiles, RoutingScorecard, receipts, decision plane.

Profiles (§142–146): economy | balanced | deep | strict | offline.
Risk can raise the minimum profile (§147), never lower it. A profile
change is policy — recorded in the routing receipt (§154) with policy
version; champion/challenger promotion is human-gated (§153).
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

SCHEMA_REQ = "platformforge/routing-request/v1"
SCHEMA_DEC = "platformforge/routing-decision/v1"
SCHEMA_SCORE = "platformforge/routing-scorecard/v1"
ROUTING_POLICY_VERSION = "platformforge/routing/v2"

PROFILES = ("economy", "balanced", "deep", "strict", "offline")
PROFILE_ORDER = {p: i for i, p in enumerate(
    ("offline", "economy", "balanced", "deep", "strict"))}

# profile → envelope hints (§143–146). Offline forbids provider calls.
PROFILE_DEFAULTS: dict[str, dict[str, Any]] = {
    "economy": {"prefer": ["deterministic", "cache", "single-specialist"],
                "context_bytes_soft": 6000, "max_agents": 1,
                "provider_calls_hard": 0, "verification_floor": "V0-static"},
    "balanced": {"prefer": ["deterministic", "single-specialist"],
                 "context_bytes_soft": 16000, "max_agents": 3,
                 "provider_calls_hard": 20,
                 "verification_floor": "V1-contract"},
    "deep": {"prefer": ["multi-specialist", "coordinated"],
             "context_bytes_soft": 30000, "max_agents": 6,
             "provider_calls_hard": 50,
             "verification_floor": "V3-integration"},
    "strict": {"prefer": ["critical-review"],
               "context_bytes_soft": 40000, "max_agents": 8,
               "provider_calls_hard": 100,
               "verification_floor": "V4-runtime"},
    "offline": {"prefer": ["deterministic"],
                "context_bytes_soft": 16000, "max_agents": 1,
                "provider_calls_hard": 0,
                "verification_floor": "V1-contract"},
}

# §147 — risk floors: the cheapest profile a risk may run under.
RISK_PROFILE_FLOOR = {"low": "economy", "medium": "balanced",
                      "high": "deep", "critical": "strict"}


@dataclass
class RoutingRequest:
    """§139 — what a task asks the routing control plane."""
    schema: str = SCHEMA_REQ
    task: str = ""
    profile: str = "balanced"
    risk: str = "low"
    signal: dict[str, Any] = field(default_factory=dict)

    def effective_profile(self) -> str:
        """§147 — risk raises the floor; it never lowers it."""
        floor = RISK_PROFILE_FLOOR.get(self.risk, "economy")
        if PROFILE_ORDER[self.profile] < PROFILE_ORDER[floor]:
            return floor
        return self.profile


@dataclass
class RoutingDecision:
    """§140–141 — the canonical routed decision."""
    schema: str = SCHEMA_DEC
    mode: str = "deterministic"
    agents: list[str] = field(default_factory=list)
    model_tier: str = "none"               # none|cheap|strong (host maps)
    context_budget: int | None = None
    tool_budget: int | None = None
    provider_budget: int | None = None
    verification_tier: str = "V0-static"
    reason: str = ""
    risk: str = "low"
    profile: str = "balanced"
    fallback: str = ""
    policy_version: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RoutingScorecard:
    """§148–149 — measured scorecard per routed run."""
    schema: str = SCHEMA_SCORE
    run_id: str = ""
    mode: str = ""
    correctness: float | None = None
    evidence: float | None = None
    tokens: int | None = None
    tools: int | None = None
    latency_ms: float | None = None
    agents: int = 0
    provider_calls: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def decide(request: RoutingRequest, *,
           routes_path: str | Path | None = None) -> RoutingDecision:
    """§139–141 — the ONLY producer of the canonical RoutingDecision.

    Wraps the deterministic router (`routing/router.py::route`) and
    applies the effective profile (risk raises the floor, never lowers).
    EconomyEngine output is *advice* that may inform `request.signal` —
    it is never a decision and never reaches orchestration. Hosts embed
    `decision.to_dict()`; the orchestrator enforces the schema.
    """
    from platformforge.routing.router import TaskSignal, route
    sig = TaskSignal.from_dict(request.signal or {})
    routed = route(sig, routes_path)
    profile = request.effective_profile()
    defaults = PROFILE_DEFAULTS.get(profile, PROFILE_DEFAULTS["balanced"])
    return RoutingDecision(
        mode=routed.get("mode", "deterministic"),
        agents=list(routed.get("agents")
                    or routed.get("specialists") or []),
        model_tier=routed.get("model_tier", "none"),
        context_budget=defaults.get("context_bytes_soft"),
        provider_budget=defaults.get("provider_calls_hard"),
        verification_tier=defaults.get("verification_floor", "V0-static"),
        reason="; ".join(routed.get("reasons", [])),
        risk=request.risk, profile=profile,
        fallback="; ".join(routed.get("fallbacks", [])),
        policy_version=ROUTING_POLICY_VERSION)


def receipt(request: RoutingRequest, decision: RoutingDecision,
            estimated_budget: dict[str, Any]) -> dict[str, Any]:
    """§154 — every routing decision records inputs + policy version +
    decision + reason + estimated budget."""
    body = {"request": request.signal, "profile": request.profile,
            "decision": decision.to_dict()}
    return {"schema": "platformforge/routing-receipt/v1",
            "inputs_hash": hashlib.sha256(json.dumps(
                body, sort_keys=True, default=str).encode()).hexdigest(),
            "policy_version": decision.policy_version,
            "decision": decision.to_dict(),
            "reason": decision.reason,
            "estimated_budget": estimated_budget,
            "ts": time.time()}


def promote_verdict(champion: dict[str, Any], challenger: dict[str, Any],
                    *, human_approved: bool = False) -> dict[str, Any]:
    """§150–153 — challenger promotes only when quality floor passes,
    safety is unchanged AND economy is better — and always behind a
    human review. Never self-modifying."""
    quality_ok = challenger.get("quality_pass", False)
    safety_ok = challenger.get("safety_unchanged", False)
    economy_better = challenger.get("economy_better", False)
    if not (quality_ok and safety_ok and economy_better):
        return {"verdict": "rejected",
                "reason": "challenger failed the gate: needs quality floor "
                          "+ unchanged safety + better economy",
                "champion_kept": True}
    if not human_approved:
        return {"verdict": "awaiting_human",
                "reason": "challenger passed all gates — promotion still "
                          "requires human review (§153)",
                "champion_kept": True}
    return {"verdict": "promotable", "champion": champion.get("id"),
            "challenger": challenger.get("id")}


def decision_receipt_link(cache_decision: dict[str, Any] | None,
                          context_ref: str | None,
                          routing_receipt: dict[str, Any],
                          verification_plan: dict[str, Any] | None,
                          budget_verdict: dict[str, Any] | None
                          ) -> dict[str, Any]:
    """§155–158 — one decision receipt links all plane decisions."""
    return {"schema": "platformforge/decision-receipt/v1",
            "cache": cache_decision, "context_ref": context_ref,
            "routing": routing_receipt, "verification": verification_plan,
            "budget": budget_verdict,
            "policy_version": routing_receipt.get("policy_version", ""),
            "ts": time.time()}
