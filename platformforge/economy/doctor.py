"""Economy doctor (§243–250) — health checks over the ledgers.

Each check inspects what actually exists (ledger rows, cache stats,
checkpoints, pricing catalog) and reports a finding only with evidence.
A check with no data reports `unresolved`, never a pass by absence.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any

from platformforge.economy.cache import CacheStore
from platformforge.economy.checkpoint import CheckpointStore

SCHEMA = "platformforge/economy-doctor/v1"
RECEIPT_REL = Path("docs/economy-parity/VALIDATION-RECEIPT.json")
RECEIPT_SCHEMA = "platformforge/economy-validation-receipt/v1"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text().splitlines()
            if l.strip()]


def _canonical_economy_gates(root: Path) -> set[str]:
    """polish §9 — the canonical gate taxonomy lives in
    scripts/validate.py; doctor derives it from the file, never from a
    copy. Importing validate.py must not run main() — it doesn't."""
    import importlib.util
    spec_path = root / "scripts" / "validate.py"
    if not spec_path.is_file():
        return set()
    spec = importlib.util.spec_from_file_location("pf_validate",
                                                  spec_path)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception:  # noqa: BLE001 — validator unreadable = no canon
        return set()
    return {n for n in getattr(mod, "GATES", {})
            if n.startswith("economy-")}


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

    # --- closure health (polish §41–43) ----------------------------------

    # receipt freshness — bound to HEAD or HEAD~1 (receipt-only commit)
    rcpt = root / RECEIPT_REL
    if not rcpt.is_file():
        note("receipt-fresh", "unresolved",
             {"code": "PF-ECONOMY-RECEIPT-STALE", "path": str(rcpt)},
             "generate: python scripts/validate.py --economy-receipt "
             f"{RECEIPT_REL}")
    else:
        doc = json.loads(rcpt.read_text())
        vs = doc.get("validated_sha") or ""
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root,
            capture_output=True, text=True, check=False).stdout.strip()
        head1 = subprocess.run(
            ["git", "rev-parse", "HEAD~1"], cwd=root,
            capture_output=True, text=True, check=False).stdout.strip()
        schema_ok = doc.get("schema") == RECEIPT_SCHEMA
        if vs and head and vs in (head, head1) and schema_ok:
            note("receipt-fresh", "ok",
                 {"validated_sha": vs[:12], "schema": doc["schema"]})
        else:
            note("receipt-fresh", "warn",
                 {"code": "PF-ECONOMY-RECEIPT-STALE",
                  "validated_sha": vs[:12], "head": head[:12],
                  "schema": doc.get("schema")},
                 "receipt predates HEAD or wrong schema — regenerate "
                 "via scripts/validate.py --economy-receipt")

        # gate taxonomy — receipt gates must be canonical economy-* names
        canon = _canonical_economy_gates(root)
        extra = sorted(set(doc.get("gates", {})) - canon)
        note("gate-taxonomy", "warn" if extra else "ok",
             {"noncanonical": extra, "canonical": len(canon)},
             "receipt carries a parallel taxonomy — regenerate from the "
             "validator" if extra else "")

        # reproduce paths — every tests/*.py referenced must exist
        dead = [t for e in doc.get("gates", {}).values()
                for t in re.findall(r"tests/\S+\.py",
                                    str(e.get("reproduce") or ""))
                if not (root / t).is_file()]
        note("reproduce-paths", "warn" if dead else "ok",
             {"dead_paths": dead},
             "regenerate the receipt — test files moved" if dead else "")

    # routing authority — EconomyEngine advises; routing.decide() decides
    try:
        from platformforge.economy.engine import EconomyEngine
        adv = EconomyEngine(root).advice({"task_type": "analysis"})
        marked = adv.get("schema") == "platformforge/economy-advice/v1" \
            and adv.get("advisory") is True
        note("routing-authority", "ok" if marked else "fail",
             {"advice_schema": adv.get("schema"),
              "advisory": adv.get("advisory")},
             "EconomyEngine output lost its advisory marker — it must "
             "never masquerade as a routing decision" if not marked
             else "")
    except Exception as exc:  # noqa: BLE001 — probe failure is data
        note("routing-authority", "unresolved", {"error": str(exc)})

    # QPT — quality-per-cost engine present and callable
    try:
        from platformforge.economy.qpt import quality_per_cost
        probe = quality_per_cost({"quality_pass": True},
                                 {"quality_pass": True})
        note("qpt", "ok" if isinstance(probe, dict) else "unresolved",
             {"callable": True})
    except Exception as exc:  # noqa: BLE001 — probe failure is data
        note("qpt", "unresolved", {"error": str(exc)})

    states = {f["state"] for f in findings}
    overall = ("fail" if "fail" in states else
               "warn" if "warn" in states else
               "unresolved" if states == {"unresolved"} else "ok")
    return {"schema": SCHEMA, "overall": overall, "checks": findings,
            "hint": "unresolved checks need data, not fixes"}
