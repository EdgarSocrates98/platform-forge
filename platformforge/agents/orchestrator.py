"""platform-orchestrator machinery — sealed TaskSpec → bounded DAG.

The orchestrator (§12) receives a sealed TaskSpec, inspects it, routes
specialists through Router V2, assembles the orchestration DAG from
canonical loop templates (rules/catalog/orchestration.yaml), applies
the run envelope, and emits a dispatch plan + run record. It is
deterministic: the model tier on its AgentSpec describes the host's
reasoning budget, not a code path here.

It never (§13): analyzes domains itself, approves mutations, executes
arbitrary actions, invents evidence, declares itself done, or verifies
its own run — `verify` is always a separate stage run by
platform-verifier.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from platformforge.agents.contracts import (
    AgentRefusal,
    AgentRunEnvelope,
    AgentRunRecord,
    PlatformTaskSpec,
    envelope_for,
    refusal,
)
from platformforge.agents.roster import AGENTS, resolve
from platformforge.agents.taskspec import require_sealed
from platformforge.models.base import stable_id
from platformforge.resources import data_path


@dataclass
class DagNode:
    stage: str
    agent: str
    depends_on: tuple[str, ...] = ()
    conditional: str = ""          # "" | conflicts | accepted
    external: bool = False         # human-gate — outside the runtime
    parallel_group: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {"stage": self.stage, "agent": self.agent,
                "depends_on": list(self.depends_on),
                "conditional": self.conditional,
                "external": self.external,
                "parallel_group": self.parallel_group}


@dataclass
class OrchestrationPlan:
    """The orchestrator's output: a DAG + envelope + run skeleton."""
    dag: list[DagNode]
    envelope: AgentRunEnvelope
    coordinator: str
    run: AgentRunRecord
    mode: str = "coordinated"
    fallbacks: tuple[str, ...] = ()
    refusal_doc: dict[str, Any] | None = None

    def topological_stages(self) -> list[list[DagNode]]:
        """Stage groups — same list may run in parallel (§79)."""
        done: set[str] = set()
        groups: list[list[DagNode]] = []
        remaining = {n.stage: n for n in self.dag}
        while remaining:
            ready = [n for n in remaining.values()
                     if all(d in done for d in n.depends_on)]
            if not ready:
                break  # cycle guard — surfaced by validate_dag upstream
            groups.append(sorted(ready, key=lambda n: n.stage))
            for n in ready:
                done.add(n.stage)
                del remaining[n.stage]
        return groups

    def to_dict(self) -> dict[str, Any]:
        return {"coordinator": self.coordinator, "mode": self.mode,
                "dag": [n.to_dict() for n in self.dag],
                "stages": [[n.stage for n in g]
                           for g in self.topological_stages()],
                "envelope": self.envelope.to_dict(),
                "run": self.run.to_dict(),
                "fallbacks": list(self.fallbacks),
                "refusal": self.refusal_doc}


def load_loops(path: str | Path | None = None) -> dict[str, Any]:
    p = Path(path) if path else data_path("rules", "catalog",
                                          "orchestration.yaml")
    doc = yaml.safe_load(p.read_text()) or {}
    return doc.get("loops", {}) or {}


def _specialists_for(domains: tuple[str, ...]) -> list[str]:
    """Routed specialists for the task's domains — must exist."""
    out = []
    for d in domains:
        for a in AGENTS.values():
            if a.role == "specialist" and d in a.domains:
                out.append(a.name)
                break
    return out


def build_dag(loop: dict[str, Any], spec: PlatformTaskSpec,
              specialists: list[str] | None = None) \
        -> tuple[list[DagNode], list[str]]:
    """Instantiate a loop template. `fanout:` stages expand to one node
    per routed specialist; a later `after: [fanout-id]` waits for ALL of
    them (§80). Returns (nodes, missing_agent_refs)."""
    specs = loop.get("stages", [])
    fanout = specialists if specialists is not None \
        else _specialists_for(spec.domains)
    if fanout == []:
        fanout = ["platform-orchestrator"]

    # pass 1 — instantiate nodes (fanout stages fan out per specialist)
    instances: list[tuple[str, DagNode]] = []
    group = 0
    for st in specs:
        if st.get("fanout"):
            group += 1
            for name in fanout:
                instances.append((st["id"], DagNode(
                    stage=f"{st['id']}:{name}", agent=name,
                    parallel_group=group,
                    conditional=st.get("if", ""))))
            continue
        agent = st.get("agent")
        external = bool(st.get("external")) or agent == "human-gate"
        instances.append((st["id"], DagNode(
            stage=st["id"], agent=agent or "?", external=external,
            conditional=st.get("if", ""))))

    # pass 2 — resolve `after` template ids to concrete stage names
    by_tid: dict[str, list[str]] = {}
    for tid, n in instances:
        by_tid.setdefault(tid, []).append(n.stage)
    missing: list[str] = []
    for st, (tid, n) in zip(
            [s for s in specs for _ in
             ([s] if not s.get("fanout") else fanout)],
            instances):
        deps = tuple(d for tid_dep in st.get("after", [])
                     for d in by_tid.get(tid_dep, []))
        n.depends_on = deps
        if n.agent != "human-gate" and not n.external \
                and resolve(n.agent) is None:
            missing.append(n.agent)
    return [n for _, n in instances], missing


def validate_dag(nodes: list[DagNode]) -> list[str]:
    """Structural checks — every dep exists, no self-deps, verifier last."""
    errs = []
    ids = {n.stage for n in nodes}
    for n in nodes:
        for d in n.depends_on:
            if d not in ids:
                errs.append(f"{n.stage} depends on missing {d}")
        if n.stage in n.depends_on:
            errs.append(f"{n.stage} depends on itself")
    verifiers = [n for n in nodes
                 if resolve(n.agent) and resolve(n.agent).role
                 == "verifier"]
    for v in verifiers:
        downstream = [n for n in nodes if v.stage in n.depends_on]
        if downstream:
            errs.append("verifier is not terminal — stages "
                        + ", ".join(n.stage for n in downstream)
                        + " depend on it")
    return errs


def prepare(spec: PlatformTaskSpec, *, loop_name: str = "platform-audit",
            router_decision: dict[str, Any] | None = None,
            specialists: list[str] | None = None,
            loops: dict[str, Any] | None = None) -> OrchestrationPlan:
    """§12 — sealed spec in, dispatch plan out. Deterministic.

    Refuses: unsealed complex spec, unknown loop, missing agents,
    structurally invalid DAG. `loops` overrides the catalog —
    used by tests and embedders; the CLI always uses the catalog."""
    complex_ = spec.complexity != "low" or spec.risk in _GOVERN_NONE
    # polish §24/§28 — a supplied router_decision must be the canonical
    # platformforge/routing-decision/v1 emitted by routing.decide().
    # EconomyEngine advice (economy-advice/v1) is refused here — it may
    # inform the signal, never activate a route.
    if router_decision:
        from platformforge.routing.decision import SCHEMA_DEC
        if router_decision.get("schema") != SCHEMA_DEC:
            run = _record(spec, dict(router_decision),
                          verdict="unresolved")
            return OrchestrationPlan(
                dag=[], envelope=envelope_for(spec.budget),
                coordinator="", run=run,
                refusal_doc=refusal(
                    AgentRefusal.ROUTE_UNRESOLVED,
                    "router_decision is not a canonical "
                    "platformforge/routing-decision/v1 — advice, raw "
                    "dicts and foreign schemas cannot activate a route",
                    "produce the decision via "
                    "platformforge.routing.decision.decide()"))
    unsealed = require_sealed(spec, complex_=complex_)
    if unsealed:
        run = _record(spec, router_decision or {}, verdict="unresolved")
        return OrchestrationPlan(dag=[], envelope=envelope_for(
            spec.budget), coordinator="", run=run,
            refusal_doc=unsealed)
    loops = load_loops() if loops is None else loops
    loop = loops.get(loop_name)
    if loop is None:
        run = _record(spec, router_decision or {}, verdict="unresolved")
        return OrchestrationPlan(
            dag=[], envelope=envelope_for(spec.budget), coordinator="",
            run=run,
            refusal_doc=refusal(
                AgentRefusal.ROUTE_UNRESOLVED,
                f"no orchestration loop named {loop_name!r}",
                "pick one of: " + ", ".join(sorted(loops))))
    nodes, missing = build_dag(loop, spec, specialists=specialists)
    errs = validate_dag(nodes)
    env = envelope_for(spec.budget)
    coordinator = loop.get("coordinator") or ""
    run = _record(spec, router_decision or {}, verdict="unresolved")
    if missing or errs:
        run = _record(spec, router_decision or {}, verdict="unresolved")
        return OrchestrationPlan(
            dag=nodes, envelope=env, coordinator=coordinator, run=run,
            refusal_doc=refusal(
                AgentRefusal.ROUTE_UNRESOLVED,
                f"loop {loop_name!r} references missing agents "
                f"{missing} or has DAG errors {errs}",
                "fix the loop template or the roster — never skip "
                "the verifier stage"))
    run.agents = tuple(sorted({n.agent for n in nodes if not n.external}))
    run.gates = tuple(n.stage for n in nodes if n.external)
    # parallel fanout charged against the envelope up front (§113)
    fanout = max((n.parallel_group for n in nodes), default=0)
    env.charge(agents=len(run.agents), fanout=max(fanout - 1, 0))
    over = env.check()
    if over:
        return OrchestrationPlan(dag=nodes, envelope=env,
                                 coordinator=coordinator, run=run,
                                 refusal_doc=over)
    return OrchestrationPlan(dag=nodes, envelope=env,
                             coordinator=coordinator, run=run,
                             mode="coordinated",
                             fallbacks=("playbook",))


_GOVERN_NONE = ("high", "critical")


def _record(spec: PlatformTaskSpec, router: dict[str, Any],
            verdict: str) -> AgentRunRecord:
    rid = stable_id("PF-RUN", spec.task_id, spec.spec_hash)
    return AgentRunRecord(run_id=rid, task_spec_hash=spec.spec_hash,
                          router_decision=router, verdict=verdict)


def checkpoint(record: AgentRunRecord,
               done_stages: tuple[str, ...]) -> dict[str, Any]:
    """§140–141 — resumable state preserving spent budget and evidence."""
    return {"run_id": record.run_id,
            "task_spec_hash": record.task_spec_hash,
            "done": list(done_stages),
            "budget_spent": record.budget,
            "evidence": list(record.evidence),
            "verdict": record.verdict}


def resume(record: AgentRunRecord, checkpoint: dict[str, Any],
           spec: PlatformTaskSpec) -> dict[str, Any] | AgentRunRecord:
    """§142 — resume revalidates before continuing; budget never resets."""
    if checkpoint.get("task_spec_hash") != spec.spec_hash:
        return refusal(
            AgentRefusal.SPEC_UNSEALED,
            "checkpoint spec hash differs from the current spec — the "
            "task changed under the run",
            "discard the checkpoint and start a new run")
    if checkpoint.get("run_id") != record.run_id:
        return refusal(
            AgentRefusal.ROUTE_UNRESOLVED,
            "checkpoint run_id does not match the record",
            "resume with the checkpoint emitted by the same run")
    record.checkpoint = dict(checkpoint)
    record.verdict = "candidate"  # resumed work is unverified until close
    return record
