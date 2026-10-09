"""Live collection economy v2 (§197–207) + fleet context funnel helpers
(§192–196).

A collection starts broad-and-cheap (inventory) and only goes deep on the
parts the graph/risk point at (§199). Every live call passes the evidence
gate first (§206–207): if local evidence can answer, the provider call
is refused — runtime truth is the only justification for spending a call.
Provider-call ROI is measured in facts gained and coverage gained per
call (§200), not money — "quality per call" claims need data (§201).
Cached observations are used while fresh (§202–203); budget exhaustion
yields partial coverage, honestly reported (§204).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from platformforge.economy.cache import CacheStore

SCHEMA = "platformforge/collection-economy-plan/v1"


@dataclass
class CollectionEconomyPlan:
    """§198 — broad → targeted, with declared caps."""
    schema: str = SCHEMA
    inventory_first: bool = True               # §199
    inventory_budget: dict[str, int] = field(
        default_factory=lambda: {"api_calls": 20, "objects": 10000})
    targeted_budget: dict[str, int] = field(
        default_factory=lambda: {"api_calls": 80, "objects": 5000})
    target_selectors: dict[str, Any] = field(default_factory=dict)
    # e.g. {"graph_nodes": [...], "risk_min": "high"}
    freshness_s: int = 3600                    # §203 cached observations
    evidence_gate: bool = True                 # §206 — always on by default

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evidence_gate(question_kind: str, local_evidence: dict[str, Any],
                  *, runtime_truth_needed: bool = False
                  ) -> dict[str, Any]:
    """§206–207 — before any live call: can local evidence answer?

    A live call is allowed only when runtime truth is needed AND local
    evidence cannot answer. Otherwise the call is refused and the caller
    is pointed at the local verbs."""
    answers = local_evidence.get("answers", [])
    coverage = local_evidence.get("coverage", 0.0)
    if runtime_truth_needed and coverage < 0.5:
        return {"decision": "live_call_justified",
                "reason": "runtime truth needed and local coverage "
                          f"{coverage:.0%} is insufficient"}
    if answers or coverage >= 0.5:
        return {"decision": "refuse_live_call",
                "reason": "local evidence can answer "
                          f"(coverage {coverage:.0%})",
                "code": "PF-ECONOMY-LIVE-UNNECESSARY",
                "use": "local artifacts/graph/facts instead"}
    return {"decision": "live_call_justified",
            "reason": "no local evidence covers the question"}


def provider_call_roi(calls: int, facts_gained: int,
                      coverage_gained: float) -> dict[str, Any]:
    """§200–201 — measured ROI in facts/coverage per call. 'Quality per
    call' conclusions require data; with no calls there is nothing."""
    if calls == 0:
        return {"state": "unresolved",
                "reason": "no calls — ROI undefined, not zero"}
    return {"calls": calls, "facts_gained": facts_gained,
            "coverage_gained": round(coverage_gained, 4),
            "facts_per_call": round(facts_gained / calls, 3),
            "coverage_per_call": round(coverage_gained / calls, 5),
            "basis": "measured"}


def coverage_on_exhaustion(collected: int, total: int
                           ) -> dict[str, Any]:
    """§204 — budget exhausted → coverage is partial and says so."""
    frac = collected / total if total else 0.0
    return {"coverage": round(frac, 4), "state": "partial",
            "code": "PF-ECONOMY-BUDGET-EXHAUSTED",
            "reason": f"collection budget exhausted at {collected}/"
                      f"{total} objects — results are partial"}


# --- fleet (§192–196) ----------------------------------------------------

def fleet_snapshot_hash(snapshot: dict[str, Any]) -> str:
    import hashlib
    import json
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True,
                                   default=str).encode()).hexdigest()


def _fleet_key(snapshot: dict[str, Any], query: str) -> str:
    # the snapshot hash is part of the KEY (not just deps): a new
    # snapshot is a different question — a miss, never a stale hit (§195)
    return f"fleet:{query}:{fleet_snapshot_hash(snapshot)[:16]}"


def fleet_query_cache_get(store: CacheStore, snapshot: dict[str, Any],
                          query: str,
                          deps: dict[str, Any] | None = None
                          ) -> dict[str, Any]:
    """§195 — cache fleet aggregates/graph queries/analytics by snapshot
    hash; a new snapshot hash is a miss, never a stale hit."""
    dec, payload = store.get("analysis", _fleet_key(snapshot, query),
                             deps or {})
    return {"decision": dec.to_dict(),
            "payload": payload}


def fleet_query_cache_put(store: CacheStore, snapshot: dict[str, Any],
                          query: str, result: Any,
                          deps: dict[str, Any] | None = None
                          ) -> dict[str, Any]:
    dec = store.put("analysis", _fleet_key(snapshot, query), result,
                    deps or {})
    return {"decision": dec.to_dict()}


def fleet_delta(snap_a: dict[str, Any], snap_b: dict[str, Any]
                ) -> dict[str, Any]:
    """§196 — snapshot delta so repeated fleet questions don't recompute.

    Members are keyed `kind:id`; the delta lists added/removed/changed
    references (member snapshots are hash references, not payloads)."""
    a = snap_a.get("members", snap_a.get("observations", {})) or {}
    b = snap_b.get("members", snap_b.get("observations", {})) or {}
    ka, kb = set(a), set(b)
    changed = sorted(k for k in ka & kb if a[k] != b[k])
    return {"snapshot_a": fleet_snapshot_hash(snap_a)[:12],
            "snapshot_b": fleet_snapshot_hash(snap_b)[:12],
            "added": sorted(kb - ka), "removed": sorted(ka - kb),
            "changed": changed,
            "unchanged": len(ka & kb) - len(changed),
            "note": "delta-first fleet reads — unchanged members keep "
                    "cached analysis"}
