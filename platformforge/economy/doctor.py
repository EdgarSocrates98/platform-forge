"""Economy doctor (§243–250) — health checks over the ledgers.

Each check inspects what actually exists (ledger rows, cache stats,
checkpoints, pricing catalog) and reports a finding only with evidence.
A check with no data reports `unresolved`, never a pass by absence.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from platformforge.economy.cache import CacheStore
from platformforge.economy.checkpoint import CheckpointStore

SCHEMA = "platformforge/economy-doctor/v1"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text().splitlines()
            if l.strip()]


def doctor(root: str | Path, *, now: float | None = None) -> dict[str, Any]:
    """Run every economy health check. `ok` is true only when no check
    produced a `warn`/`fail` — unresolved checks don't fake health."""
    now = now if now is not None else time.time()
    root = Path(root)
    led = root / ".platformforge" / "ledger"
    findings: list[dict[str, Any]] = []

    def note(check: str, state: str, evidence: dict[str, Any],
             fix: str = "") -> None:
        findings.append({"check": check, "state": state,
                         "evidence": evidence, "recommended_fix": fix})

    # --- cache disabled ------------------------------------------------
    store = CacheStore(root / ".platformforge" / "cache")
    stats = store.stats()
    if stats["entries"] == 0 and stats["hits"] == 0 and \
            stats["misses"] == 0:
        note("cache-enabled", "warn", {"stats": stats},
             "cache store is empty — reuse is not happening")
    else:
        note("cache-enabled", "ok", {"entries": stats["entries"]})

    # --- cache hit rate ------------------------------------------------
    total = stats["hits"] + stats["misses"]
    if total >= 10:
        rate = stats["hits"] / total
        note("cache-hit-rate", "warn" if rate < 0.3 else "ok",
             {"hit_rate": round(rate, 3), "samples": total},
             "investigate dep churn or key scope" if rate < 0.3 else "")
    else:
        note("cache-hit-rate", "unresolved",
             {"samples": total, "reason": "too few lookups to judge"})

    # --- context oversized ----------------------------------------------
    econ = _read_jsonl(led / "economy.jsonl")
    builds = [e for e in econ if e.get("tool") == "context.build"]
    if builds:
        biggest = max(e.get("output_bytes", 0) for e in builds)
        note("context-size", "warn" if biggest > 100_000 else "ok",
             {"max_context_bytes": biggest, "builds": len(builds)},
             "narrow scope or raise detail via refs" if biggest > 100_000
             else "")
    else:
        note("context-size", "unresolved", {"builds": 0})

    # --- provider calls --------------------------------------------------
    prov = _read_jsonl(led / "provider.jsonl") + [
        e for e in econ if e.get("entry_type") == "provider"]
    if prov:
        calls = sum(e.get("api_calls", e.get("calls", 0)) or 0
                    for e in prov)
        note("provider-calls", "warn" if calls > 50 else "ok",
             {"api_calls": calls, "entries": len(prov)},
             "check evidence_gate — local evidence may answer")
    else:
        note("provider-calls", "unresolved", {"entries": 0})

    # --- stale checkpoints ----------------------------------------------
    cps = CheckpointStore(root / ".platformforge" / "checkpoints")
    names = cps.list()
    stale = []
    for n in names:
        cp = cps.load(n)
        if cp and now - cp.created_at > 7 * 86400:
            stale.append(n)
    note("stale-checkpoints",
         "warn" if stale else "ok",
         {"checkpoints": len(names), "stale_7d": stale},
         "gc or resume — spend may be double-counted" if stale else "")

    # --- missing pricing ---------------------------------------------------
    econ_missing = [e for e in econ
                    if e.get("code") == "PF-ECONOMY-PRICING-MISSING" or
                    e.get("refusal") == "PF-ECONOMY-PRICING-MISSING"]
    note("pricing", "warn" if econ_missing else "ok",
         {"missing_pricing_events": len(econ_missing)},
         "declare a pricing row" if econ_missing else "")

    states = {f["state"] for f in findings}
    overall = ("fail" if "fail" in states else
               "warn" if "warn" in states else
               "unresolved" if states == {"unresolved"} else "ok")
    return {"schema": SCHEMA, "overall": overall, "checks": findings,
            "hint": "unresolved checks need data, not fixes"}
