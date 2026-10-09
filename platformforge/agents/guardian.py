"""platform-release-guardian — deterministic closure review (§27).

Evaluates gates/tests/evals/lab/docs/package/receipts/versioning/
compatibility/known-gaps from MEASURED inputs and returns READY or an
explicit blocker list. The guardian never runs the gates itself — the
CLI feeds it gate results; it never fudges a missing signal into a pass.
"""

from __future__ import annotations

from typing import Any

REQUIRED_SIGNALS = ("tests", "evals", "lab", "docs_drift", "package",
                    "gates")


def release_review(signals: dict[str, Any],
                   known_gaps: tuple[str, ...] = ()) -> dict[str, Any]:
    """signals: {tests: {"pass": n, "fail": n}, evals: {...}, lab: {...},
    docs_drift: bool(pass), package: bool, gates: {name: ok},
    receipts: {...}, versioning: str, compatibility: [notes]}"""
    blockers: list[str] = []
    missing = [s for s in REQUIRED_SIGNALS if s not in signals]
    for s in missing:
        blockers.append(f"missing signal: {s} — unmeasured is not passed")
    t = signals.get("tests") or {}
    if t.get("fail", 0) or t.get("unresolved", 0):
        blockers.append(f"tests: {t.get('fail', 0)} failed, "
                        f"{t.get('unresolved', 0)} unresolved")
    for s in ("evals", "lab"):
        v = signals.get(s) or {}
        if v.get("fail", 0) or v.get("unresolved", 0):
            blockers.append(f"{s}: fail={v.get('fail', 0)} "
                            f"unresolved={v.get('unresolved', 0)}")
    if signals.get("docs_drift") is False:
        blockers.append("docs drift gate failing")
    if signals.get("package") is False:
        blockers.append("package gate failing")
    gates = signals.get("gates") or {}
    for name, ok in gates.items():
        if not ok:
            blockers.append(f"gate failed: {name}")
    return {"verdict": "READY" if not blockers else "BLOCKED",
            "blockers": blockers,
            "known_gaps": list(known_gaps),
            "signals_seen": sorted(signals),
            "note": "READY requires every signal measured; absent "
                    "signals are blockers, not assumptions"}
