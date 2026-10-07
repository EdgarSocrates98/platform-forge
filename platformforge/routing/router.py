"""Adaptive routing.

Route = f(task type, complexity, risk, evidence availability, domain,
blast radius, security sensitivity, cost impact). The table lives in
rules/catalog/routing.yaml — data, not judgment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class TaskSignal:
    task_type: str = "analysis"        # lint|analysis|review|incident|architecture|change
    domains: list[str] = field(default_factory=list)
    complexity: str = "low"            # low|medium|high
    risk: str = "low"                  # low|medium|high|critical
    blast_radius: str = "local"        # local|service|platform|org
    security_sensitive: bool = False
    evidence_available: bool = True
    production: bool = False
    expected_cost: str = "low"             # low|medium|high (§37)
    evidence_completeness: float = 1.0     # 0-1 measured fraction

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> TaskSignal:
        return cls(**{k: v for k, v in d.items()
                      if k in cls.__dataclass_fields__})


DEFAULT_ROUTE = {
    "mode": "deterministic",
    "agents": [],
    "reason": "no rule matched — deterministic engine is the default",
}

BUILTIN_ROUTES = [
    {"when": {"task_type": "lint"}, "mode": "deterministic", "agents": []},
    {"when": {"task_type": "incident"},
     "mode": "coordinated",
     "agents": ["incident-coordinator"],
     "then": "relevant specialists by evidence"},
    {"when": {"security_sensitive": True},
     "add_agents": ["security-reviewer"], "reason": "security mandatory"},
    {"when": {"task_type": "architecture", "blast_radius": ["platform", "org"]},
     "mode": "coordinated",
     "agents": ["platform-coordinator", "architecture-reviewer"]},
    {"when": {"task_type": "change", "production": True},
     "mode": "coordinated",
     "agents": ["change-risk-reviewer"]},
    {"when": {"task_type": "analysis", "complexity": ["medium", "high"]},
     "mode": "specialist"},
]


def _match(sig: TaskSignal, when: dict[str, Any]) -> bool:
    for k, want in when.items():
        have = getattr(sig, k, None)
        if isinstance(want, list):
            if have not in want:
                return False
        elif have != want:
            return False
    return True


def load_routes(path: str | Path | None = None) -> list[dict[str, Any]]:
    from platformforge.resources import data_path
    if path and Path(path).is_file():
        doc = yaml.safe_load(Path(path).read_text()) or {}
        return doc.get("routes", []) or []
    default = data_path("rules", "catalog", "routing.yaml")
    if default.is_file():
        doc = yaml.safe_load(default.read_text()) or {}
        return doc.get("routes", []) or []
    return BUILTIN_ROUTES


def route(signal: TaskSignal, routes_path: str | Path | None = None) -> dict[str, Any]:
    """Compute the dispatch plan. Returns mode + ordered agents + why."""
    routes = load_routes(routes_path)
    agents: list[str] = []
    mode = "deterministic"
    reasons: list[str] = []
    extra: list[str] = []

    for r in routes:
        if _match(signal, r.get("when", {})):
            if r.get("mode") and mode == "deterministic":
                mode = r["mode"]
            for a in r.get("agents", []):
                if a not in agents:
                    agents.append(a)
            for a in r.get("add_agents", []):
                if a not in agents:
                    agents.append(a)
            if r.get("reason"):
                reasons.append(r["reason"])
            if r.get("then"):
                extra.append(r["then"])

    # deterministic escalation rules (not data — policy)
    if signal.task_type in ("analysis", "review") and mode == "deterministic" \
            and signal.domains:
        mode = "specialist"
        for d in signal.domains:
            a = f"{d}-specialist"
            if a not in agents:
                agents.append(a)
    if signal.complexity == "high" and mode == "specialist":
        mode = "coordinated"
        agents.insert(0, f"{signal.domains[0] if signal.domains else 'platform'}-coordinator")
    if not signal.evidence_available or signal.evidence_completeness < 0.5:
        extra.append("evidence unavailable — expect named unresolved, not guesses")
    if signal.expected_cost == "high":
        extra.append("high expected cost — deterministic-first mandated")

    return {
        "mode": mode,
        "agents": agents,
        "next": extra,
        "reasons": reasons or ["matched route table"],
        "signal": {k: getattr(signal, k) for k in signal.__dataclass_fields__},
    }
