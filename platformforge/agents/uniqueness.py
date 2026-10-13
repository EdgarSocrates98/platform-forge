"""Agent fan-out economy (§117–129): uniqueness audit + selective
agentics helpers.

Per-run audit measures who actually contributed — unique vs duplicated
vs refuted vs discarded contribution (§118). An agent that adds nothing
is a candidate for routing reduction (§119) — a recommendation, never
auto-applied (§115). No leaderboard: agents are graded as contribution
records, not ranked as people (§120).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class AgentContribution:
    agent: str
    contribution_ids: list[str] = field(default_factory=list)
    # finding/artifact ids the agent uniquely produced
    refuted: list[str] = field(default_factory=list)
    discarded: list[str] = field(default_factory=list)


@dataclass
class AgentUniqueness:
    """§117 — per-run fanout audit."""
    run_id: str = ""
    agents_invoked: list[str] = field(default_factory=list)
    unique_contribution: dict[str, list[str]] = field(default_factory=dict)
    duplicated_contribution: dict[str, list[str]] = field(
        default_factory=dict)
    refuted_contribution: dict[str, list[str]] = field(default_factory=dict)
    discarded_contribution: dict[str, list[str]] = field(
        default_factory=dict)
    findings: list[dict[str, Any]] = field(default_factory=list)

    def audit(self, contributions: list[AgentContribution]
              ) -> AgentUniqueness:
        """Classify each agent's output ids: an id claimed by ≥2 agents is
        duplicated for the later claimants; refuted/discarded buckets come
        from the contribution rows themselves."""
        seen: dict[str, str] = {}
        for c in contributions:
            self.agents_invoked.append(c.agent)
            unique, dup = [], []
            for cid in c.contribution_ids:
                if cid in seen:
                    dup.append(cid)
                else:
                    seen[cid] = c.agent
                    unique.append(cid)
            if unique:
                self.unique_contribution[c.agent] = unique
            if dup:
                self.duplicated_contribution[c.agent] = dup
            if c.refuted:
                self.refuted_contribution[c.agent] = list(c.refuted)
            if c.discarded:
                self.discarded_contribution[c.agent] = list(c.discarded)
            if not unique and not c.refuted and not c.discarded \
                    and not dup:
                self.findings.append({
                    "waste_type": "unused_agent", "agent": c.agent,
                    "confidence": "high",
                    "evidence": "invoked with zero contribution ids",
                    "recommended_fix": "review routing rule — candidate "
                                       "for fanout reduction"})
            elif not unique and (dup or c.refuted or c.discarded):
                self.findings.append({
                    "waste_type": "unused_agent", "agent": c.agent,
                    "confidence": "medium",
                    "evidence": "all contribution ids duplicated, "
                                "refuted or discarded",
                    "recommended_fix": "routing review — contribution "
                                       "overlapped entirely"})
        return self

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["agents_invoked_count"] = len(self.agents_invoked)
        d["unique_ratio"] = (
            sum(len(v) for v in self.unique_contribution.values()) /
            max(1, sum(len(v) for v in self.unique_contribution.values())
                + sum(len(v) for v in self.duplicated_contribution.values())))
        return d


# §123 — selective agentics policy (data, not judgment).
def suggested_fanout(task_type: str, domains: list[str], risk: str,
                     conflict: bool = False) -> dict[str, Any]:
    """simple → ≤1 specialist; cross-domain → multi; conflict/high-risk
    → debate/review. Mirrors the Router V2 policy as an economy check."""
    if conflict or risk in ("high", "critical"):
        mode, agents = "debate-or-review", 3
    elif len(domains) > 1:
        mode, agents = "multi-specialist", min(len(domains), 4)
    elif task_type in ("lint", "inventory", "policy", "diff"):
        mode, agents = "deterministic", 0
    else:
        mode, agents = "single-specialist", 1
    return {"mode": mode, "suggested_max_agents": agents,
            "reason": "§123 selective agentics"}


def fanout_verdict(envelope_check: dict[str, Any], requested_agents: int,
                   max_agents: int | None) -> dict[str, Any]:
    """§122/§246 — fanout may never exceed the envelope's hard limit."""
    if max_agents is not None and requested_agents > max_agents:
        return {"refusal": "PF-ECONOMY-BUDGET-EXHAUSTED",
                "reason": f"fanout {requested_agents} > max_agents "
                          f"{max_agents}",
                "dimension": "fanout"}
    return {"decision": "ok", "fanout": requested_agents}
