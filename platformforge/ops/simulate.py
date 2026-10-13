"""Cycle 4 — simulation engine (§24–30).

Simulation is first-class and *level-honest*: S0 static → S5 authorized
cloud sandbox. A simulation receipt records level, inputs, environment,
expected delta, unknowns and unsupported behaviors. "Simulation passed"
never means "production safe" — limitations are part of the output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from platformforge.live.models import now_iso
from platformforge.ops.models import ChangePlan

SIMULATION_LEVELS = ("S0", "S1", "S2", "S3", "S4", "S5")
LEVEL_NAMES = {
    "S0": "static",
    "S1": "local-deterministic",
    "S2": "sandbox/process",
    "S3": "local-infra/kind/container",
    "S4": "provider-dry-run/plan",
    "S5": "authorized-cloud-sandbox"}

# What each level can honestly claim.
LEVEL_LIMITS = {
    "S0": ["no runtime behavior", "no controller semantics",
           "schema/shape only"],
    "S1": ["deterministic projection — no provider calls"],
    "S2": ["process isolation — no real provider"],
    "S3": ["local cluster only — not production topology"],
    "S4": [("dry-run/plan covers API validation, not controller "
            "behavior or drift convergence")],
    "S5": ["sandbox account — production data/scale not covered"]}


@dataclass
class SimulationReceipt:
    level: str = "S0"
    environment: str = "local"
    inputs: dict[str, Any] = field(default_factory=dict)
    expected_delta: dict[str, Any] = field(default_factory=dict)
    outcome: str = "unknown"         # pass|fail|partial|unknown
    findings: list[str] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)
    unsupported: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    ran_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"schema": "platformforge/simulation-receipt/v1",
                "level": self.level,
                "level_name": LEVEL_NAMES.get(self.level, "?"),
                "environment": self.environment,
                "outcome": self.outcome,
                "expected_delta": self.expected_delta,
                "findings": self.findings, "unknowns": self.unknowns,
                "unsupported": self.unsupported,
                "limitations": self.limitations, "ran_at": self.ran_at}


def simulate(plan: ChangePlan, *, level: str = "S1",
             observed_graph: dict[str, Any] | None = None,
             planned_graph: dict[str, Any] | None = None,
             executor_results: list[dict[str, Any]] | None = None
             ) -> SimulationReceipt:
    """Deterministic local simulation:
    - validates the plan DAG (cycles/deps),
    - computes graph delta when both graphs are given (S1),
    - folds in executor dry-run results when provided (S4 class),
    - always emits the level's limitations.
    """
    if level not in SIMULATION_LEVELS:
        level = "S0"
    r = SimulationReceipt(level=level, ran_at=now_iso(),
                          expected_delta=plan.expected_delta.to_dict(),
                          limitations=list(LEVEL_LIMITS.get(level, [])),
                          inputs={"plan_hash": plan.hash(),
                                  "steps": len(plan.steps)})

    v = plan.validate()
    for item in v:
        r.findings.append(f"plan:{item['refusal']}")
    if v:
        r.outcome = "fail"
        return r

    # S1: graph delta from observed → planned projection
    if observed_graph is not None and planned_graph is not None:
        on = set((observed_graph.get("nodes") or {}).keys())
        pn = set((planned_graph.get("nodes") or {}).keys())
        oe = set((observed_graph.get("edges") or {}).keys())
        pe = set((planned_graph.get("edges") or {}).keys())
        r.expected_delta["adds"] = {
            "resources": sorted(pn - on), "dependencies": sorted(pe - oe)}
        r.expected_delta["removes"] = {
            "resources": sorted(on - pn), "dependencies": sorted(oe - pe)}
        r.unknowns.extend([d for d in ("security", "slo", "cost")
                           if d not in
                           (plan.expected_delta.to_dict() or {})])
    else:
        r.unknowns.append("graph-delta:not-computed "
                          "(graphs not supplied)")

    for er in executor_results or []:
        if not er.get("ok", er.get("rc") == 0):
            r.findings.append(
                f"executor:{er.get('action', '?')} failed/dry-run rc≠0")
        if er.get("unsupported"):
            r.unsupported.extend(er["unsupported"])

    if r.findings:
        r.outcome = "fail"
    elif r.unknowns or r.unsupported:
        r.outcome = "partial"
    else:
        r.outcome = "pass"
    return r


def assertion() -> str:
    """§30 — the sentence every simulation output implies."""
    return ("simulation passed != production safe — receipt declares "
            "level, limits and unknowns")
