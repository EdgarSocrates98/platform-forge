"""§122 rule coverage report + §127 false-positive measurement.

Coverage: which eval variants exercise each catalog rule.
Precision: cases carrying `expect.rules_not_fired` measure whether a rule
fires where it shouldn't — precision = rules that stayed silent on
negative/boundary fixtures / total negative+boundary observations.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from platformforge.evals.runner import CASES_DIR, _catalog, _facts_for, _fired_ids
from platformforge.lab.runner import SCENARIOS_DIR

VARIANTS = ("positive", "negative", "boundary", "unresolved", "version")


def _case_docs(cases_dir: Path) -> list[tuple[Path, dict]]:
    out = []
    for c in sorted(cases_dir.glob("*/case.yaml")) if cases_dir.is_dir() \
            else []:
        doc = yaml.safe_load(c.read_text()) or {}
        out.append((c.parent, doc))
    return out


def _lab_docs(scenarios_dir: Path) -> list[tuple[Path, dict]]:
    out = []
    for e in sorted(scenarios_dir.glob("*/expected.yaml")) \
            if scenarios_dir.is_dir() else []:
        doc = yaml.safe_load(e.read_text()) or {}
        out.append((e.parent, doc))
    return out


def _rules_of(case: dict) -> dict[str, list[str]]:
    """Every rule a case exercises, keyed by expectation polarity."""
    exp = case.get("expect", {})
    return {"positive": list(exp.get("rules_fired", [])),
            "negative": list(exp.get("rules_not_fired", [])),
            "version": list(exp.get("version_notes", []))}


def _lab_rules_of(doc: dict) -> dict[str, list[str]]:
    """A lab scenario covers every rule it asserts on."""
    return {"positive": list(doc.get("violated_rules", [])),
            "negative": list(doc.get("absent_rules", []))}


def rule_coverage(cases_dir: str | Path = CASES_DIR,
                  scenarios_dir: str | Path = SCENARIOS_DIR) \
        -> dict[str, Any]:
    """rule_id → {variant: [cases]}. Eval cases AND lab scenarios count —
    a rule asserted by a lab `violated_rules` is covered-positive; by
    `absent_rules`, covered-negative. Uncovered rules are named."""
    catalog = _catalog()
    matrix: dict[str, dict[str, list[str]]] = {
        r.rule_id: {v: [] for v in VARIANTS} for r in catalog}
    for cdir, case in _case_docs(Path(cases_dir)):
        cid = case.get("id", cdir.name)
        variant = case.get("variant")
        for rid, polarity in _rules_of(case).items():
            for r in polarity:
                if r in matrix:
                    if variant in VARIANTS:
                        matrix[r][variant].append(cid)
                    elif polarity in VARIANTS:
                        matrix[r][polarity].append(cid)
                    else:
                        matrix[r]["positive"].append(cid)
    for sdir, doc in _lab_docs(Path(scenarios_dir)):
        sid = f"lab/{sdir.name}"
        for polarity, rules in _lab_rules_of(doc).items():
            for r in rules:
                if r in matrix:
                    matrix[r][polarity].append(sid)
    rows = []
    for rid in sorted(matrix):
        cov = matrix[rid]
        rows.append({"rule_id": rid,
                     **{v: bool(cov.get(v)) for v in VARIANTS},
                     "cases": sum(len(v) for v in cov.values())})
    covered = [r for r in rows if r["cases"] > 0]
    return {"coverage": rows,
            "counts": {"rules": len(rows), "with_cases": len(covered),
                       "uncovered": sorted(r["rule_id"] for r in rows
                                           if r["cases"] == 0)},
            "note": "coverage = a case or lab scenario names the rule; "
                    "it is not a correctness proof"}


def precision_report(cases_dir: str | Path = CASES_DIR) -> dict[str, Any]:
    """§127 — run every case, measure per-rule false-positive rate.

    A false positive = a rule fires on a negative/boundary case that lists
    it under `rules_not_fired`. Reported per rule and in aggregate."""
    per_rule: dict[str, dict[str, int]] = {}
    details = []
    for cdir, case in _case_docs(Path(cases_dir)):
        not_fired = set(case.get("expect", {}).get("rules_not_fired", []))
        if not not_fired:
            continue
        try:
            fired = _fired_ids(_facts_for(case, cdir),
                               case.get("versions"))
        except Exception as exc:  # noqa: BLE001 — case error ≠ FP
            details.append({"case": cdir.name, "error": str(exc)})
            continue
        fps = not_fired & fired
        for rid in not_fired:
            d = per_rule.setdefault(rid, {"fp": 0, "checks": 0})
            d["checks"] += 1
            d["fp"] += int(rid in fps)
        if fps:
            details.append({"case": cdir.name,
                            "false_positives": sorted(fps)})
    rows = []
    for rid, d in sorted(per_rule.items()):
        rows.append({"rule_id": rid, "false_positives": d["fp"],
                     "negative_checks": d["checks"],
                     "precision": round(1 - d["fp"] / d["checks"], 4)
                     if d["checks"] else None})
    total_fp = sum(r["false_positives"] for r in rows)
    total_checks = sum(r["negative_checks"] for r in rows)
    return {"precision": rows,
            "aggregate_precision": round(1 - total_fp / total_checks, 4)
            if total_checks else None,
            "details": details,
            "counts": {"rules_measured": len(rows),
                       "negative_checks": total_checks,
                       "false_positives": total_fp},
            "note": "precision measured on negative/boundary cases only; "
                    "no negative corpus → no precision claim"}
