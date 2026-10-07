"""QPT benchmark suite (cycle 2.1 §43–46) — fixed task corpus.

Each case dir carries `case.yaml` (id, task, domain, budget, versions) and a
`fixture/`. Every task runs the SAME pipeline: analyze → facts → index →
full vs TokenSave-packed envelopes → same judge, same rules, same versions.
Emits per-task receipts plus an aggregate verdict; a machine-readable
receipt is written when `out` is given.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import yaml

from platformforge.economy.qpt import quality_per_token
from platformforge.tokensave.budget import Budget
from platformforge.tokensave.index import SearchIndex


def _analyze(domain: str, fixture: Path):
    from platformforge.lab.runner import _ANALYZERS, _resolve
    fn = _resolve(_ANALYZERS[domain])
    return fn(fixture)


def run_qpt_bench(bench_dir: str | Path | None = None) -> dict[str, Any]:
    from platformforge.resources import data_path
    root = Path(bench_dir) if bench_dir else data_path("evals", "qpt-bench")
    results: list[dict[str, Any]] = []
    for case_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        case = yaml.safe_load((case_dir / "case.yaml").read_text()) or {}
        fixture = case_dir / case.get("fixture", "fixture")
        out = _analyze(case["domain"], fixture)
        facts = out.get("facts", [])
        with tempfile.TemporaryDirectory() as td:
            idx = SearchIndex(Path(td) / "i.db")
            idx.index_workspace(fixture)
            rep = quality_per_token(
                facts_full=facts, findings_full=[],
                index=idx, task=case.get("task", case_dir.name),
                versions=case.get("versions"),
                budget=Budget(input_budget=case.get("budget", 50_000)))
        rep = rep.get("qpt", rep) if rep.get("budget_decision") == "refuse" else rep
        results.append({"id": case.get("id", case_dir.name),
                        "task": case.get("task"),
                        "domain": case["domain"],
                        "facts": len(facts),
                        "verdict": rep.get("verdict"),
                        "token_reduction": rep.get("economy", rep)
                            .get("token_reduction"),
                        "quality": rep.get("quality"),
                        "receipt": rep})
    agg = {
        "tasks": len(results),
        "verdicts": {v: sum(1 for r in results if r["verdict"] == v)
                     for v in ("beneficial", "no_reduction",
                               "optimization_not_beneficial")},
        "min_finding_recall": min(
            (r["quality"]["finding_recall"] for r in results if r["quality"]),
            default=None),
        "min_evidence_recall": min(
            (r["quality"]["evidence_recall"] for r in results if r["quality"]),
            default=None),
    }
    return {"cases": results, "aggregate": agg}
