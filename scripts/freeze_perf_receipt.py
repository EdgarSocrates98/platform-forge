#!/usr/bin/env python3
"""§96–§103 — PERFORMANCE-RECEIPT generator.

Runs the measured scale benchmark, times the common CLI commands, and
writes docs/freeze/PERFORMANCE-RECEIPT.json bound to the current HEAD.
Regression is RELATIVE (percent vs the stored baseline), never
absolute — hardware differs, direction matters.

Usage: python scripts/freeze_perf_receipt.py [--write]
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RECEIPT = REPO / "docs" / "freeze" / "PERFORMANCE-RECEIPT.json"
BASELINE = REPO / "docs" / "freeze" / "PERFORMANCE-BASELINE.json"

COMMANDS = [
    ["platformforge", "--help"],
    ["platformforge", "doctor"],
    ["platformforge", "inspect", "--repo", "."],
    ["platformforge", "agents", "list"],
    ["platformforge", "capability", "manifest"],
]

# relative thresholds (§100): a run >20% slower than baseline on the
# same host flags a regression candidate — a review signal, not a gate
REGRESSION_PCT = 20.0


def _time(cmd: list[str]) -> dict:
    t0 = time.time()
    p = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True,
                       check=False)
    return {"cmd": " ".join(cmd), "rc": p.returncode,
            "ms": round((time.time() - t0) * 1000, 1)}


def command_sweep() -> list[dict]:
    return [_time(c) for c in COMMANDS]


def regression(current: dict, baseline: dict) -> dict:
    """Compare measured fields present in both receipts."""
    flags = []
    for size, cur in current.get("sizes", {}).items():
        base = baseline.get("sizes", {}).get(size)
        if not base or base.get("status") != "measured" \
                or cur.get("status") != "measured":
            continue
        for k in ("build_ms", "diff_ms", "serialize_ms",
                  "peak_build_kib"):
            if k in cur and k in base and base[k]:
                pct = (cur[k] - base[k]) / base[k] * 100
                if pct > REGRESSION_PCT:
                    flags.append(f"{size}.{k}: +{pct:.0f}% vs baseline")
    return {"regression_flags": flags,
            "verdict": "pass" if not flags else "flagged",
            "threshold_pct": REGRESSION_PCT}


def main() -> int:
    write = "--write" in sys.argv
    sys.path.insert(0, str(REPO))
    from platformforge.graph.bench import run_scale_benchmarks

    rep = run_scale_benchmarks(
        sizes=(1_000, 10_000, 25_000, 50_000, 100_000),
        edge_targets=(10_000, 50_000, 100_000, 250_000,
                      500_000, 1_000_000),
        store_sweep=True)
    receipt = {
        "schema": "platformforge/performance-receipt/v1",
        "sha": rep["environment"]["commit"],
        "environment": rep["environment"],
        "graph": rep,
        "commands": command_sweep(),
    }
    if BASELINE.exists():
        receipt["regression"] = regression(rep, json.loads(
            BASELINE.read_text())["graph"])
    else:
        receipt["regression"] = {"note": "no baseline — first receipt "
                                         "becomes the baseline"}
    if write:
        RECEIPT.write_text(json.dumps(receipt, indent=2,
                                      sort_keys=True) + "\n")
        print(f"written {RECEIPT}")
        if not BASELINE.exists():
            BASELINE.write_text(json.dumps(receipt, indent=2,
                                           sort_keys=True) + "\n")
            print(f"baseline recorded {BASELINE}")
    else:
        print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
