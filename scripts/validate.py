#!/usr/bin/env python3
"""Cycle 2.1 §143–147 — single validation source.

CI orchestrates this script; it does not re-implement gates. Locally:

    python scripts/validate.py              # all gates → receipt JSON
    python scripts/validate.py --gate lint  # one gate
    python scripts/validate.py --receipt out.json

Every failure is explainable (§147): the gate reports what failed, why,
how to reproduce (`reproduce` field), and how to unlock.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _run(cmd: list[str], cwd: Path = REPO) -> dict:
    t0 = time.time()
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                       check=False)
    return {"cmd": " ".join(cmd), "rc": p.returncode,
            "seconds": round(time.time() - t0, 2),
            "tail": (p.stdout + p.stderr).strip().splitlines()[-5:]}


def _py(expr: str) -> dict:
    return _run([sys.executable, "-c", expr])


def gate_lint() -> dict:
    return _run(["ruff", "check", "."])


def gate_tests() -> dict:
    return _run(["pytest", "-q"])


def gate_provenance() -> dict:
    r = _py("from platformforge.rules.engine import catalog_provenance_report;"
            "r = catalog_provenance_report('rules/catalog');"
            "assert r['coverage'] == 1.0, r; print(r)")
    r["what"] = "every rule cites >=1 source"
    return r


def gate_linkage() -> dict:
    r = _py("from platformforge.knowledge.registry import SourceRegistry;"
            "from platformforge.resources import data_path;"
            "r = SourceRegistry.default().link_rules(data_path('rules','catalog'));"
            "assert not r['unlinked'], r['unlinked'];"
            "assert not r['bad_refs'], r['bad_refs'];"
            "print(r['coverage'], 'exact-id linked')")
    r["what"] = "rule sources resolve by canonical id — no fuzzy matching"
    return r


def gate_knowledge() -> dict:
    r = _py("from platformforge.knowledge.registry import (SourceRegistry, "
            "SOURCE_AUTHORITIES);"
            "reg = SourceRegistry.default();"
            "c = reg.contract_check(); assert c['ok'], c;"
            "bad = [e.id for e in reg.entries.values() "
            "     if e.source_authority not in SOURCE_AUTHORITIES];"
            "assert not bad, f'unknown authority: {bad}';"
            "print(len(reg.entries), 'sources valid')")
    r["what"] = "source registry contract + closed authority vocabulary"
    return r


def gate_packs() -> dict:
    r = _py("from platformforge.knowledge.packs import PackRegistry;"
            "c = PackRegistry.default().contract_check();"
            "assert c['ok'], c;"
            "print(c['packs'], 'packs,', c['consumed'], 'consumed')")
    r["what"] = "knowledge packs resolve sources+rules+analyzers; "
    "none unconsumed"
    return r


def gate_lab() -> dict:
    return _run(["platformforge", "lab", "run-all"])


def gate_evals() -> dict:
    # --strict: an eval case regressing to `unresolved` fails the gate
    return _run(["platformforge", "evals", "run", "--strict"])


def gate_coverage() -> dict:
    return _run(["platformforge", "evals", "coverage"])


def gate_mcp_parity() -> dict:
    r = _py("from platformforge.mcp.registry import tool_descriptors;"
            "t = tool_descriptors(); assert len(t) >= 20, len(t);"
            "print(len(t), 'mcp tools')")
    r["what"] = "MCP tool surface registered"
    return r


def gate_docs() -> dict:
    return _run(["pytest", "-q", "tests/test_docs_drift.py"])


def gate_security() -> dict:
    r = _run(["pytest", "-q", "tests/test_redaction.py",
              "tests/test_offline.py"])
    r["what"] = "redaction coverage + offline enforcement"
    return r


def gate_package() -> dict:
    """Wheel contents + clean-env smoke. Requires `python -m build` first;
    skipped gracefully when dist/ is absent."""
    if not list(REPO.glob("dist/*.whl")):
        return {"rc": 0, "skipped": "no dist/*.whl — run python -m build",
                "what": "wheel contains bundled data"}
    r = _py("import zipfile, glob;"
            "w = zipfile.ZipFile(glob.glob('dist/*.whl')[0]);"
            "names = w.namelist();"
            "need = ('platformforge/data/rules/catalog/',"
            "        'platformforge/data/knowledge/sources.yaml',"
            "        'platformforge/data/contracts/fact.schema.json',"
            "        'platformforge/data/lab/scenarios/',"
            "        'platformforge/data/evals/cases/');"
            "miss = [n for n in need "
            "        if not any(x.startswith(n) for x in names)];"
            "assert not miss, miss;"
            "print(sum(1 for x in names if '/data/' in x), 'data files')")
    r["what"] = "wheel ships rules/knowledge/contracts/lab/evals data"
    return r


GATES = {
    "lint": gate_lint, "tests": gate_tests, "provenance": gate_provenance,
    "linkage": gate_linkage, "knowledge": gate_knowledge,
    "packs": gate_packs, "lab": gate_lab, "evals": gate_evals,
    "coverage": gate_coverage, "mcp-parity": gate_mcp_parity,
    "docs": gate_docs, "security": gate_security, "package": gate_package,
}

UNLOCK = {
    "lint": "ruff check --fix . or fix the reported lines",
    "tests": "reproduce: pytest -q; fix the failing test or the code",
    "provenance": "add a canonical `sources:` id to the uncovered rule",
    "linkage": "use a registry `id:` (not a URL); fix `source_refs` keys",
    "knowledge": "complete required entry fields; fix source_authority",
    "packs": "resolve pack refs or remove the unconsumed pack",
    "lab": "platformforge lab run-all; fix the failing scenario/expected.yaml",
    "evals": "platformforge evals run; fix case or graded behavior",
    "coverage": "add an eval/lab case naming the uncovered rule",
    "mcp-parity": "register the missing tool in mcp/registry.py",
    "docs": "update docs to name the real verb (tests/test_docs_drift.py)",
    "security": "keep redaction before index/compress; fix the pattern or FP",
    "package": "check pyproject force-include map; rebuild wheel",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate", choices=sorted(GATES))
    ap.add_argument("--receipt", help="write machine-readable receipt JSON")
    args = ap.parse_args()

    names = [args.gate] if args.gate else list(GATES)
    receipt = {"kind": "platformforge/validation-receipt/1",
               "sha": _run(["git", "rev-parse", "HEAD"])["tail"][-1:]
                      if not args.gate else None,
               "gates": {}}
    failed = []
    for name in names:
        res = GATES[name]()
        ok = res.get("rc", 1) == 0
        entry = {"ok": ok, "reproduce": res.get("cmd", "n/a"),
                 "seconds": res.get("seconds")}
        if res.get("skipped"):
            entry["skipped"] = res["skipped"]
        if not ok:
            entry["why"] = res.get("tail", [])[-3:]
            entry["unlock"] = UNLOCK.get(name, "see the gate output")
            failed.append(name)
        receipt["gates"][name] = entry
        print(f"{'PASS' if ok else 'FAIL'} {name}", file=sys.stderr)

    receipt["verdict"] = "validated" if not failed else "failed"
    receipt["failed"] = failed
    if args.receipt or not args.gate:
        out = json.dumps(receipt, indent=2, sort_keys=True)
        if args.receipt:
            Path(args.receipt).write_text(out)
        else:
            print(out)
    return 0 if not failed else 2


if __name__ == "__main__":
    sys.exit(main())
