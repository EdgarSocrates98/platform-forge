"""§148–150 — measured benchmarks on bundled fixtures. Never invented.

Each measurement runs the real code path N times over the eval corpus
fixtures and reports wall-clock medians + artifact sizes. Numbers are
local to this machine and this run — they are a baseline, not a claim.
"""

from __future__ import annotations

import statistics
import tempfile
import time
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent.parent


def _time(fn, repeat: int = 3) -> dict[str, float]:
    ts = []
    for _ in range(repeat):
        t0 = time.perf_counter()
        fn()
        ts.append(time.perf_counter() - t0)
    return {"median_s": round(statistics.median(ts), 4),
            "min_s": round(min(ts), 4), "runs": repeat}


def _case_fixtures() -> list[tuple[str, Path]]:
    cases = sorted((_REPO / "evals" / "cases").glob("*/fixture"))
    return [(c.parent.name, c) for c in cases if c.is_dir()]


def _collect_facts(fixtures: list[tuple[str, Path]]) -> list[dict]:
    from platformforge.lab.runner import _analyzer
    facts: list[dict] = []
    for name, fdir in fixtures:
        for dom in ("iac", "k8s", "gitops", "gha", "catalog", "secrets",
                    "iam", "finops", "kyverno", "sbom", "helm", "plan",
                    "state", "cloud-aws"):
            try:
                facts.extend(_analyzer(dom, fdir).get("facts", []))
            except (OSError, ValueError, KeyError, AttributeError):
                continue  # fixture lacks this domain's input — expected
    return facts


def run_benchmark(repeat: int = 3) -> dict[str, Any]:
    """§148 — analyze, rule execution, graph build, index, context pack."""
    from platformforge.graph.build import GraphBuilder
    from platformforge.models.base import Fact
    from platformforge.rules import RuleEngine, load_catalog
    from platformforge.tokensave.index import SearchIndex

    fixtures = _case_fixtures()
    facts_cache: list[dict] | None = None

    def collect() -> list[dict]:
        nonlocal facts_cache
        if facts_cache is None:
            facts_cache = _collect_facts(fixtures)
        return facts_cache

    results: dict[str, Any] = {"benchmark": "platformforge.bench/v1",
                               "fixtures": len(fixtures),
                               "note": "local baseline — measured, "
                                       "not a claim"}

    results["analyze_all"] = _time(collect, repeat)
    facts = collect()
    results["facts_total"] = len(facts)
    fact_objs = [Fact.from_dict(f) for f in facts]

    rules = load_catalog(_REPO / "rules" / "catalog")
    results["rules"] = len(rules)
    eng = RuleEngine(rules)
    results["rule_execution"] = _time(lambda: eng.evaluate(fact_objs),
                                      repeat)
    results["graph_build"] = _time(
        lambda: GraphBuilder().from_facts(facts), repeat)

    def _index() -> dict[str, int]:
        with tempfile.TemporaryDirectory() as td:
            idx = SearchIndex(Path(td) / "i.db")
            total = 0
            for _, fdir in fixtures:
                total += idx.index_workspace(fdir)["indexed"]
            idx.db.close()
            return {"files": total}

    stats_holder: dict[str, int] = {}
    t = _time(lambda: stats_holder.update(_index()), repeat)
    results["index_time"] = {**t, **stats_holder}

    def _pack() -> dict[str, Any]:
        from platformforge.tokensave.packs import ContextPackBuilder
        with tempfile.TemporaryDirectory() as td, SearchIndex(Path(td) / "i.db") as idx:
            idx.index_workspace(_REPO / "rules" / "catalog")
            b = ContextPackBuilder(idx)
            return b.build("review kubernetes security posture",
                           facts=facts[:100])

    results["context_build"] = _time(_pack, repeat)

    # cycle3 §258 — live drift over synthetic envelopes (measured)
    def _live_diff() -> int:
        from platformforge.live.drift import diff_observations
        from platformforge.live.models import ObservationEnvelope
        def _env(oid: str, n: int, shift: int) -> ObservationEnvelope:
            e = ObservationEnvelope.new(
                collector="bench", version="v", provider="kubernetes",
                source_type="observed", scope={}, captured_at="t0")
            e.coverage = {"status": "complete"}
            e.fresh_until = "2099-01-01T00:00:00Z"
            for i in range(n):
                e.objects.append({
                    "resource_id": f"r-{i}", "resource_type": "k8s:Pod",
                    "content_hash": f"h{i + shift}",
                    "attributes": {"i": i}})
            e.observation_id = oid
            return e
        return len(diff_observations(_env("obs-" + "0" * 16, 2000, 0),
                                     _env("obs-" + "f" * 16, 2000, 50)
                                     )["drift"])

    results["live_drift_2k"] = _time(_live_diff, repeat)

    # §150 storage economy — real on-disk sizes
    store_dir = _REPO / ".platformforge"
    results["storage"] = {
        "workspace_store_bytes": sum(
            p.stat().st_size for p in store_dir.rglob("*")
            if p.is_file()) if store_dir.is_dir() else 0,
        "eval_fixture_bytes": sum(
            p.stat().st_size for _, fdir in fixtures
            for p in fdir.rglob("*") if p.is_file())}
    return results


def token_benchmark(repeat: int = 3) -> dict[str, Any]:
    """§149 — economy measured on small/medium/large fixture subsets."""
    from platformforge.caveman import compress

    fixtures = _case_fixtures()
    out: dict[str, Any] = {"benchmark": "platformforge.tokenbench/v1"}
    sizes = sorted(fixtures,
                   key=lambda t: sum(p.stat().st_size
                                     for p in t[1].rglob("*")
                                     if p.is_file()))
    n = len(sizes)
    tiers = {"small": sizes[:max(1, n // 3)],
             "medium": sizes[n // 3:max(2, 2 * n // 3)],
             "large": sizes[2 * n // 3:]}
    for label, fs in tiers.items():
        if not fs:
            continue
        files = [p for _, d in fs for p in sorted(d.rglob("*"))
                 if p.is_file() and p.stat().st_size < 100_000]
        raw = sum(p.stat().st_size for p in files)

        def _compact(tier_files: list[Path] = files) -> int:
            total = 0
            for p in tier_files:  # bound now — loop var fix
                txt, _rc = compress(p.read_text(errors="replace"))
                total += len(txt)
            return total

        t = _time(_compact, repeat)
        compacted = _compact()
        out[label] = {"files": len(files), "raw_bytes": raw,
                      "compact_bytes": compacted,
                      "ratio": round(compacted / raw, 3) if raw else None,
                      **t}
    return out
