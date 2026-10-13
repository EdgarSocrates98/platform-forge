#!/usr/bin/env python3
"""§M — VALIDATION-RECEIPT generator.

Runs the full gate suite (scripts/validate.py) and the freeze-critical
verbs, then writes docs/freeze/VALIDATION-RECEIPT.json bound to the
exact HEAD it was generated against. Must be the LAST artifact produced:
any later code change invalidates it.

Usage: python scripts/freeze_validation_receipt.py [--write]
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RECEIPT = REPO / "docs" / "freeze" / "VALIDATION-RECEIPT.json"


def _run(cmd: list[str]) -> dict:
    t0 = time.time()
    p = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True,
                       check=False)
    return {"cmd": " ".join(cmd), "rc": p.returncode,
            "ms": round((time.time() - t0) * 1000, 1),
            "tail": p.stdout.strip().splitlines()[-1:] or
            p.stderr.strip().splitlines()[-1:]}


def main() -> int:
    write = "--write" in sys.argv
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                         check=False, capture_output=True,
                         text=True).stdout.strip()
    gates = _run([sys.executable, "scripts/validate.py"])
    receipt = {
        "schema": "platformforge/validation-receipt/v1",
        "sha": sha,
        "note": "sha is the HEAD the suite ran against; the commit that "
                "lands this receipt is docs-only",
        "gates": gates,
        "gates_ok": gates["rc"] == 0,
        "receipts_present": {n: (REPO / "docs" / "freeze" / n).exists()
                             for n in ("PERFORMANCE-RECEIPT.json",
                                       "SOAK-RECEIPT.json",
                                       "AGENTIC-RECEIPT.json",
                                       "FREEZE-MANIFEST.md",
                                       "FINAL-MATRIX.md",
                                       "FINAL-REPORT.md",
                                       "ARCHITECTURE-FREEZE-REVIEW.md",
                                       "REAL-WORLD-ISSUES.md")},
    }
    receipt["verdict"] = "pass" if (
        receipt["gates_ok"]
        and all(receipt["receipts_present"].values())) else "fail"
    if write:
        RECEIPT.write_text(json.dumps(receipt, indent=2,
                                      sort_keys=True) + "\n")
        print(f"written {RECEIPT} verdict={receipt['verdict']} sha={sha[:8]}")
    else:
        print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["verdict"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
