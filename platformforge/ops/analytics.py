"""Cycle 4 §172–175, §250–254 — LEARN phase: roll stored operations up
into honest, reproducible analytics.

Everything here derives *only* from the append-only store — no external
telemetry, no estimates. Absent data is reported as absent, never zero.
"""

from __future__ import annotations

from typing import Any

from platformforge.live.models import now_iso, parse_ts
from platformforge.ops.store import OperationStore

ANALYTICS_SCHEMA = "platformforge/ops-analytics/v1"


def operation_analytics(store: OperationStore) -> dict[str, Any]:
    """Roll up every stored operation into outcome/economy metrics."""
    ops = store.list_operations()
    by_state: dict[str, int] = {}
    events: dict[str, int] = {}
    per_action: dict[str, dict[str, int]] = {}
    durations_s: list[float] = []
    terminal = {"converged", "failed", "rolled-back", "cancelled",
                "expired"}
    succeeded = failed = rolled = denied = 0
    for op_id in ops:
        op = store.load_operation(op_id)
        led = store.load_ledger(op_id)
        state = op.state if op else "unknown"
        by_state[state] = by_state.get(state, 0) + 1
        if state == "converged":
            succeeded += 1
        elif state == "rolled-back":
            rolled += 1
        elif state == "failed":
            failed += 1
        for e in led.entries:
            events[e.event] = events.get(e.event, 0) + 1
            act = (e.data or {}).get("action")
            if act and e.event.startswith("step."):
                a = per_action.setdefault(
                    act, {"started": 0, "completed": 0, "failed": 0})
                if e.event == "step.started":
                    a["started"] += 1
                elif e.event == "step.completed":
                    a["completed"] += 1
                elif e.event == "step.failed":
                    a["failed"] += 1
            if e.event == "approval.denied":
                denied += 1
        # duration from history transitions
        if op and len(op.history) >= 2:
            t0 = parse_ts(op.history[0].get("at", ""))
            t1 = parse_ts(op.history[-1].get("at", ""))
            if t0 and t1 and t1 >= t0:
                durations_s.append((t1 - t0).total_seconds())
    closed = succeeded + failed + rolled
    return {
        "schema": ANALYTICS_SCHEMA,
        "generated_at": now_iso(),
        "operations": {
            "total": len(ops), "by_state": by_state,
            "terminal": sum(by_state.get(s, 0) for s in terminal),
            "converged": succeeded, "failed": failed,
            "rolled_back": rolled,
            "success_rate": (succeeded / closed if closed else None),
            "rollback_rate": (rolled / closed if closed else None)},
        "approvals": {"denied": denied},
        "ledger_events": events,
        "per_action": per_action,
        "durations_s": {
            "count": len(durations_s),
            "avg": (sum(durations_s) / len(durations_s)
                    if durations_s else None),
            "max": max(durations_s) if durations_s else None},
        "notes": [
            ("derived from the local append-only store only — "
             "a remote host's operations are not visible"),
            ("success/rollback rates are None (not zero) when no "
             "terminal operations exist"),
        ]}
