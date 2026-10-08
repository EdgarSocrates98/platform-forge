"""§57–§62 — deterministic, offline replay.

Reuses lab/runner analyzer dispatch (fixture → facts → RuleEngine).
Grading: violated/absent rules + fact kinds vs expected_known_truth.
Output includes a canonical hash — replay twice, hashes must match.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

import yaml

from platformforge.cases.casefile import CaseFile, case_errors, discover_cases

SCHEMA = "platformforge/case-replay/v1"


def _fixture_dir(c: CaseFile) -> Path:
    if c.fixture_from:
        return Path(c.fixture_from) / "fixture"
    return c.path.parent / "fixture"


def _run_case(c: CaseFile) -> dict[str, Any]:
    """One deterministic pass: analyzers → facts → findings."""
    from platformforge.lab.runner import CATALOG, _analyzer
    from platformforge.models import Fact
    from platformforge.rules import RuleEngine, load_catalog

    fixture = _fixture_dir(c)
    facts: list[dict[str, Any]] = []
    errors = []
    for dom in c.analyzers:
        try:
            facts += _analyzer(dom, fixture)["facts"]
        except Exception as e:  # noqa: BLE001 — analyzer failure is a case error
            errors.append(f"{dom}: {e}")
    rule_facts = [Fact.from_dict(f) for f in facts]
    findings, skipped = RuleEngine(load_catalog(CATALOG)).evaluate(rule_facts)
    violated = sorted({f.rule_id for f in findings if f.status == "violated"})
    kinds = sorted({f.kind for f in rule_facts})
    canonical = json.dumps({"violated": violated, "kinds": kinds,
                            "errors": sorted(errors)}, sort_keys=True)
    return {"violated": violated, "kinds": kinds,
            "errors": errors, "skipped_rules": len(skipped),
            "hash": hashlib.sha256(canonical.encode()).hexdigest()}


def replay_case(c: CaseFile) -> dict[str, Any]:
    errs = case_errors(c)
    if errs:
        return {"case": c.id, "verdict": "unresolved",
                "errors": errs}
    exp = c.expected_known_truth
    t0 = time.time()
    r1 = _run_case(c)
    r2 = _run_case(c)  # §62 — determinism: identical canonical result
    deterministic = r1["hash"] == r2["hash"]

    failures = []
    want_v = set(exp.get("violated_rules", []))
    want_absent = set(exp.get("absent_rules", []))
    want_kinds = set(exp.get("fact_kinds", []))
    got_v = set(r1["violated"])
    got_k = set(r1["kinds"])
    failures += [f"expected violated missing: {r}" for r in sorted(want_v - got_v)]
    failures += [f"unexpected violation: {r}" for r in sorted(want_absent & got_v)]
    failures += [f"expected fact kind missing: {k}"
                 for k in sorted(want_kinds - got_k)]
    # FP/FN accounting vs declared truth (§65)
    false_positives = sorted(got_v - want_v)
    false_negatives = sorted(want_v - got_v)
    if not deterministic:
        failures.append("nondeterministic replay: hash mismatch")
    verdict = "pass" if not failures and not r1["errors"] else "fail"
    return {"schema": SCHEMA, "case": c.id, "tier": c.tier,
            "classification": c.classification,
            "truth_class": c.truth_class,
            "verdict": verdict, "deterministic": deterministic,
            "failures": failures, "analyzer_errors": r1["errors"],
            "violated": r1["violated"], "fact_kinds": r1["kinds"],
            "false_positives": false_positives,
            "false_negatives": false_negatives,
            "result_hash": r1["hash"], "ms": round((time.time() - t0) * 1000, 1)}


def replay_all(root: str | Path = ".platformforge/cases",
               tier: str | None = None) -> dict[str, Any]:
    cases = discover_cases(root)
    if tier:
        cases = [c for c in cases if c.tier == tier]
    results = [replay_case(c) for c in cases]
    by_tier: dict[str, dict[str, int]] = {}
    for r in results:
        t = by_tier.setdefault(r["tier"], {"pass": 0, "fail": 0,
                                           "unresolved": 0, "total": 0})
        t[r["verdict"]] = t.get(r["verdict"], 0) + 1
        t["total"] += 1
    failed = [r["case"] for r in results if r["verdict"] == "fail"]
    corpus_hash = hashlib.sha256(json.dumps(
        [(r["case"], r.get("result_hash", "")) for r in results],
        sort_keys=True).encode()).hexdigest()
    return {"schema": "platformforge/case-corpus/v1",
            "cases": results, "by_tier": by_tier,
            "corpus_hash": corpus_hash,
            "verdict": "pass" if not failed and results else "fail",
            "failed": failed,
            "note": "golden = development corpus; holdout = never tuned "
                    "against — report both, merge neither"}


def validate_corpus(root: str | Path = ".platformforge/cases"
                    ) -> dict[str, Any]:
    """Structure-only check — every case.yaml satisfies §54."""
    cases = discover_cases(root)
    bad = {c.id: case_errors(c) for c in cases}
    bad = {k: v for k, v in bad.items() if v}
    return {"cases": len(cases), "invalid": bad,
            "verdict": "pass" if cases and not bad else "fail"}


def write_case_template(path: str | Path) -> None:
    Path(path).write_text(yaml.safe_dump({
        "id": "case-<n>",
        "classification": "fixture-derived",
        "tier": "golden",
        "truth_class": "known-bad",
        "task": "<one-line task the operator ran>",
        "scope": "<repo/platform slice>",
        "analyzers": ["k8s"],
        "fixture_from": "lab/scenarios/<id>",
        "expected_known_truth": {
            "violated_rules": [], "absent_rules": [], "fact_kinds": []},
        "observations": [],
        "agent_route": {"selected": [], "rejected": [], "fanout": 0},
        "context_cost": {"input_bytes": 0, "relevant_bytes": 0},
        "verdict": "unresolved",
    }, sort_keys=False, allow_unicode=True))
