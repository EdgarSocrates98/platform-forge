"""Agentic strategy benchmark (§118–121, §197–198).

Six fixed tasks routed under each strategy mode. What we measure NOW
is deterministic: agents dispatched, fanout, budget class, DAG depth —
the *cost side*. Quality claims (correctness, evidence recall, false
positives) only become measurable when AgentRunLedger has real run
rows; this bench never fabricates those — it reports `measured` vs
`projected` honestly (§119: do not assume multi-agent is better —
prove it, with data, not vibes).
"""

from __future__ import annotations

from typing import Any

from platformforge.routing import TaskSignal, route

# §198 — the benchmark task set, fixed.
BENCH_TASKS: dict[str, TaskSignal] = {
    "terraform-review": TaskSignal(task_type="review", domains=["iac"],
                                   complexity="low", risk="low"),
    "k8s-drift": TaskSignal(task_type="analysis", domains=["k8s"],
                            complexity="medium"),
    "aws-security": TaskSignal(task_type="review", domains=["aws"],
                               security_sensitive=True, risk="high"),
    "incident": TaskSignal(task_type="incident", domains=["k8s", "sre"],
                           incident_status="active", risk="high"),
    "fleet-optimization": TaskSignal(task_type="analysis",
                                     domains=["fleet", "finops"],
                                     optimization=True,
                                     fleet_scope=True),
    "platform-audit": TaskSignal(task_type="analysis",
                                 domains=["iac", "k8s", "aws",
                                          "security", "finops"],
                                 complexity="high"),
}


def run_agent_bench() -> dict[str, Any]:
    """Projected cost per task per mode — honest projection, not a
    measured-quality claim. Real quality comparison lands in the run
    ledger once runs exist (§118–121)."""
    per_task: dict[str, Any] = {}
    for name, sig in BENCH_TASKS.items():
        got = route(sig)
        n_agents = (len(got["specialists"]) + len(got["reviewers"])
                    + bool(got["coordinator"]) + bool(got["verifier"]))
        per_task[name] = {
            "mode": got["mode"], "budget": got["budget"],
            "agents": n_agents, "specialists": len(got["specialists"]),
            "reviewers": len(got["reviewers"]),
            "dag_stages": len(got["dag"]),
            "verifier": bool(got["verifier"]),
            "measured": "projected",
            "note": "cost projection from router output — quality "
                    "comparison needs real run rows (§119)"}
    return {"tasks": per_task, "strategies_compared":
            ["deterministic", "single-specialist", "multi-specialist",
             "coordinated", "debate"],
            "verdict": "benchmark is projection-only until run ledger "
                       "has observed rows — no quality claim made"}
