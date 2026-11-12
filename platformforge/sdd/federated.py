"""Federated SDD adapters — platformforge → forge/* contracts (Onda 5A).

Converts native SDD artifacts (gates, receipts, evidence) into the
versioned federated shapes declared in
``the-forge/docs/portable-installation/schemas/``. Additive only: the
native engine is untouched; a consumer that cannot read a contract simply
gets fewer shapes — absence is never invented.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

#: native phase → canonical phase (spec §7.3 — semantic mapping, the
#: engine keeps its own names; the adapter translates at the boundary).
PHASE_MAP = {
    "discover": "explore",
    "define": "define",
    "design": "design",
    "contract": "design",
    "plan": "plan",
    "build": "build_report",
    "review": "verify",
    "verify": "verify",
    "ship": "ship",
    "learn": "learn",
    "explore": "explore",
    "build_report": "build_report",
}

_PHASES = ("explore", "define", "design", "plan", "build_report", "verify",
           "ship", "learn")


def map_phase(native: str) -> str:
    """Canonical phase for a native phase name. Unknown phases map to
    themselves only when already canonical — anything else is reported
    verbatim by callers (never silently relabeled)."""
    return PHASE_MAP.get(native, native if native in _PHASES else native)


def _item(raw: dict[str, Any], feature: str) -> dict[str, Any]:
    """Native refused/unresolved item → ForgeSDDGate/v1 item."""
    item: dict[str, Any] = {"code": str(raw.get("code") or "unknown")}
    item["feature"] = str(raw.get("feature") or feature)
    # native uses ``phase`` where the contract uses ``path``; both are the
    # artifact locator — keep whichever exists, null otherwise.
    item["path"] = raw.get("path") or raw.get("phase")
    item["field"] = raw.get("field")
    if raw.get("unlock"):
        item["unlock"] = str(raw["unlock"])
    return item


def to_gate(feature: str, phase: str, gate_result: dict[str, Any],
            *, evaluator: str = "platformforge") -> dict[str, Any]:
    """Native ``check()``/``ship_gate()`` result → ``forge/SDDGate/v1``."""
    return {
        "schema": "forge/SDDGate/v1",
        "feature": feature,
        "phase": map_phase(phase),
        "ok": bool(gate_result.get("ok", False)),
        "refused": [_item(r, feature) for r in gate_result.get("refused") or ()],
        "unresolved": [
            _item(r, feature) for r in gate_result.get("unresolved") or ()
        ],
        "evaluator": evaluator,
    }


def to_evidence(path: str | Path, *, kind: str, agent: str,
                command: list[str], covers: list[str] | None = None,
                sha256: str | None = None) -> dict[str, Any]:
    """Artifact reference → ``forge/Evidence/v1`` (sha computed when the
    file exists and no digest was supplied)."""
    from platformforge.core.hashing import sha256_file

    p = Path(path)
    if sha256 is None and p.is_file():
        sha256 = f"sha256:{sha256_file(p)}"
    out: dict[str, Any] = {
        "schema": "forge/Evidence/v1",
        "id": p.stem,
        "kind": kind,
        "path": str(path),
        "produced_by": {"agent": agent, "command": list(command)},
        "covers": list(covers or []),
    }
    if sha256:
        out["sha256"] = sha256
    return out


def to_receipt(feature: str, phase: str, action: str, actor: str,
               recorded_at: str, *, verdict: str | None = None,
               outputs: list[str] | None = None,
               inputs_sha256: list[str] | None = None,
               rollback_ref: str | None = None,
               override: dict[str, Any] | None = None) -> dict[str, Any]:
    """Phase completion → ``forge/SDDReceipt/v1``."""
    out: dict[str, Any] = {
        "schema": "forge/SDDReceipt/v1",
        "feature": feature,
        "phase": map_phase(phase),
        "action": action,
        "actor": actor,
        "recorded_at": recorded_at,
    }
    if verdict is not None:
        out["verdict"] = verdict
    if outputs:
        out["outputs"] = list(outputs)
    if inputs_sha256:
        out["inputs_sha256"] = list(inputs_sha256)
    if rollback_ref:
        out["rollback_ref"] = rollback_ref
    if override:
        out["override"] = dict(override)
    return out


def federated_view(feature_dir: str | Path, *, feature: str,
                   agent: str = "platformforge") -> dict[str, Any]:
    """Best-effort projection of a feature dir into contract shapes.

    Emits only what exists: a feature dir without receipts produces no
    receipts. Returned dict keys are the contract ``$id`` strings."""
    root = Path(feature_dir)
    out: dict[str, list[dict[str, Any]]] = {
        "forge/Evidence/v1": [],
        "forge/SDDReceipt/v1": [],
    }
    receipts = root / "receipts"
    if receipts.is_dir():
        for f in sorted(receipts.glob("*.json")):
            try:
                doc = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(doc, dict) and doc.get("schema", "").startswith(
                "forge/SDDReceipt"
            ):
                out["forge/SDDReceipt/v1"].append(doc)
    return {k: v for k, v in out.items() if v}
