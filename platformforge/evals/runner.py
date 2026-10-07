"""Eval runner — evals/cases/*.yaml, offline, deterministic.

Each case maps a type to a real check:

- golden/unit/integration/regression → analyze a fixture, judge, compare
  `expect.rules_fired`/`rules_not_fired`
- recall/precision → expected rule set vs observed set, `threshold`
- contract → validate a doc against contracts/*.schema.json
- token_economy → context pack respects `--input-budget`
- routing → `route(TaskSignal)` mode matches `expect.mode`
- graph_correctness → build graph from fixture facts, assert dependents
  or blast membership
- security → scan_secrets output must not contain `must_not_contain`
- property/metamorphic → transform invariants (rtk compact→expand round-trip)

Unknown type → verdict `unresolved` (declared, never silently passed).
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import yaml

EVAL_TYPES = ("unit", "integration", "golden", "contract", "property",
              "metamorphic", "regression", "recall", "precision",
              "token_economy", "graph_correctness", "routing", "security")
VARIANTS = ("positive", "negative", "boundary", "unresolved", "version")

_REPO = Path(__file__).resolve().parents[2]
CASES_DIR = _REPO / "evals" / "cases"


def _catalog():
    from platformforge.rules import load_catalog
    return load_catalog(_REPO / "rules")


def _facts_for(case: dict, case_dir: Path) -> list[dict]:
    dom = case.get("domain", "k8s")
    fx = case_dir / case.get("fixture", "fixture")
    from platformforge.lab.runner import _analyzer
    return _analyzer(dom, fx)["facts"]


def _fired_ids(facts: list[dict]) -> set[str]:
    from platformforge.models import Fact
    from platformforge.rules import RuleEngine
    fs = [f if isinstance(f, Fact) else Fact.from_dict(f) for f in facts]
    findings, _skipped = RuleEngine(_catalog()).evaluate(fs)
    return {f.rule_id for f in findings if f.status == "violated"}


def _grade_analyze(case: dict, case_dir: Path) -> dict[str, Any]:
    fired = _fired_ids(_facts_for(case, case_dir))
    exp = case.get("expect", {})
    missing = sorted(set(exp.get("rules_fired", [])) - fired)
    extra = sorted(fired & set(exp.get("rules_not_fired", [])))
    ok = not missing and not extra
    return {"verdict": "pass" if ok else "fail", "fired": sorted(fired),
            "missing": missing, "unexpected": extra}


def _grade(case: dict, case_dir: Path) -> dict[str, Any]:
    t = case.get("type", "golden")
    exp = case.get("expect", {})
    if t in ("golden", "unit", "integration", "regression"):
        return _grade_analyze(case, case_dir)
    if t in ("recall", "precision"):
        fired = _fired_ids(_facts_for(case, case_dir))
        want = set(exp.get("rules_fired", []))
        tp = len(fired & want)
        val = (tp / len(want)) if t == "recall" and want else \
              (tp / len(fired)) if fired else 0.0
        thr = exp.get("threshold", 1.0)
        return {"verdict": "pass" if val >= thr else "fail",
                t: val, "fired": sorted(fired), "expected": sorted(want)}
    if t == "contract":
        import jsonschema
        schema = json.loads((_REPO / "contracts" / exp["schema"])
                            .read_text())
        doc = yaml.safe_load((case_dir / case["fixture"]).read_text())
        errs = [e.message for e in
                jsonschema.Draft7Validator(schema).iter_errors(doc)]
        return {"verdict": "pass" if not errs else "fail", "errors": errs}
    if t == "graph_correctness":
        facts = _facts_for(case, case_dir)
        from platformforge.graph import GraphBuilder
        g = GraphBuilder().from_facts(facts).graph
        node = exp["node"]
        if "dependents_of" in exp:
            from platformforge.graph.query import dependents
            got = sorted(dependents(g, node))
            return {"verdict": "pass" if got == sorted(exp["dependents_of"])
                    else "fail", "got": got}
        if "blast_of" in exp:
            from platformforge.graph.query import blast_radius
            got = sorted(blast_radius(g, node)["nodes"])
            return {"verdict": "pass" if got == sorted(exp["blast_of"])
                    else "fail", "got": got}
        return {"verdict": "unresolved",
                "reason": "no graph assertion in expect"}
    if t == "routing":
        from platformforge.routing import TaskSignal, route
        got = route(TaskSignal.from_dict(case["signal"]))
        ok = got.get("mode") == exp.get("mode")
        return {"verdict": "pass" if ok else "fail", "mode": got.get("mode"),
                "agents": got.get("agents")}
    if t == "token_economy":
        from platformforge.tokensave.budget import Budget
        from platformforge.tokensave.index import SearchIndex
        from platformforge.tokensave.packs import ContextPackBuilder
        with tempfile.TemporaryDirectory() as td:
            idx = SearchIndex(Path(td) / "i.db")
            idx.index_workspace(case_dir / case.get("fixture", "fixture"))
            pack = ContextPackBuilder(idx, None).build(
                task=case.get("query", ""),
                budget=Budget(input_budget=exp["budget"]))
        over = pack["est_input_tokens"] > exp["budget"]
        refused = bool(pack.get("refusals"))
        return {"verdict": "pass" if not over or refused else "fail",
                "est_input_tokens": pack["est_input_tokens"],
                "refusals": pack.get("refusals")}
    if t == "security":
        from platformforge.security import scan_secrets
        out = scan_secrets(case_dir / case.get("fixture", "fixture"))
        blob = json.dumps(out, default=str)
        leaked = [v for v in exp.get("must_not_contain", []) if v in blob]
        return {"verdict": "pass" if not leaked else "fail",
                "leaked": leaked}
    if t in ("property", "metamorphic"):
        if exp.get("check") == "rtk_round_trip":
            from platformforge.core.store import ArtifactStore
            from platformforge.rtk import compact_output
            from platformforge.rtk.compact import expand
            text = (case_dir / case["fixture"]).read_text()
            with tempfile.TemporaryDirectory() as td:
                store = ArtifactStore(td)
                res = compact_output("cat", text, store=store)
                full = expand(store, res.raw_artifact)
            ok = "\n".join(l.split(": ", 1)[1] for l in full["lines"]) == \
                text.rstrip("\n")
            return {"verdict": "pass" if ok else "fail"}
        return {"verdict": "unresolved",
                "reason": f"unknown property check {exp.get('check')!r}"}
    return {"verdict": "unresolved", "reason": f"unimplemented type {t}"}


def run_case(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    case = yaml.safe_load(p.read_text())
    res = _grade(case, p.parent)
    return {"id": case.get("id", p.stem), "type": case.get("type", "golden"),
            "variant": case.get("variant"), "case_of": case.get("case_of"),
            **res}


def run_all(cases_dir: str | Path = CASES_DIR,
            type_filter: str | None = None) -> dict[str, Any]:
    d = Path(cases_dir)
    # one dir per case: <cases>/<id>/case.yaml + fixture/ (fixture yaml
    # files never collide with the case file name)
    results = []
    for c in sorted(d.glob("*/case.yaml")) if d.is_dir() else []:
        r = run_case(c)
        if type_filter and r["type"] != type_filter:
            continue
        results.append(r)
    counts = {"pass": 0, "fail": 0, "unresolved": 0}
    for r in results:
        counts[r["verdict"] if r["verdict"] in counts else "unresolved"] += 1
    return {"evals": len(results), "results": results, "counts": counts}
