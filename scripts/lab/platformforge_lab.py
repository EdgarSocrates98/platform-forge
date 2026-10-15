#!/usr/bin/env python3
"""Forge Lab emitter — runs platformforge.lab.runner.run_all (static profile)
and emits forge/BenchmarkResult/v1. Deterministic, offline, stdlib-only.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

FORGE = "platform-forge"
SUITE = "platform-forge-lab"


import re as _re


def _slug(s: object) -> str:
    return _re.sub(r"[^a-z0-9-]+", "-", str(s).lower()).strip("-") or "scenario"


def m(state: str, value: object = None, unit: str = "") -> dict:
    return {"state": state, "unit": unit, "value": value}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkout", required=True)
    ap.add_argument("--mode", default="A", choices=["A", "B", "C"])
    ap.add_argument("--result-out", required=True)
    a = ap.parse_args()
    checkout = Path(a.checkout).resolve()
    sys.path.insert(0, str(checkout))

    import os

    os.chdir(checkout)  # scenario fixtures resolve relative to repo root
    from platformforge.lab.runner import run_all

    started = time.monotonic()
    data = run_all("static")
    elapsed = int((time.monotonic() - started) * 1000)

    results = []
    seen_ids: dict[str, int] = {}
    for r in data.get("scenarios", []):
        failures = r.get("failures", []) or []
        counts = r.get("counts", {}) or {}
        base = _slug(f"{r.get('scenario', 'unknown')}-{r.get('tier', '')}-{r.get('profile', '')}")
        seen_ids[base] = seen_ids.get(base, 0) + 1
        sid = base if seen_ids[base] == 1 else f"{base}-{seen_ids[base]}"
        results.append(
            {
                "scenario_id": sid,
                "verdict": "pass" if r.get("passed") else "fail",
                "duration_ms": elapsed,
                "detail": "; ".join(str(f) for f in failures[:3]),
                "evidence_ref": "",
                "judge": None,
                "metrics": {
                    "success": m("measured", 1.0 if r.get("passed") else 0.0, "ratio"),
                    "false_positives": m("measured", len(failures)),
                    "evidence_coverage": m("measured", counts.get("facts"), "facts")
                    if counts.get("facts") is not None
                    else m("not_available"),
                    "cost_usd": m("not_applicable"),
                    "tokens": m("not_applicable"),
                },
            }
        )

    receipt = {
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "external": False,
        "suite": SUITE,
        "forge": FORGE,
        "mode": a.mode,
        "notes": [
            "profile=static",
            f"skipped_profile_guard={len(data.get('skipped_profile_guard', []))}",
        ],
        "producer": {"id": FORGE, "version": "lab-script"},
        "results": results,
    }
    out = Path(a.result_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
