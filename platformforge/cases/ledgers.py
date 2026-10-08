"""§64–§68 — false-positive / false-negative ledgers.

A ledger entry is a claim about a *finding* (rule verdict), never a
repo bug. Every reproducible failure carries a `regression_test`
pointer that must resolve to a case or test — the gate enforces it.
Precision is computed only when ground truth exists (§68).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

ROOT_CAUSES = (
    "missing-extractor", "bad-normalization", "bad-identity",
    "bad-scope", "stale-knowledge", "rule-too-broad", "rule-too-narrow",
    "graph-gap", "agent-reasoning", "routing-failure",
    "context-omission", "provider-limitation",
)

LEDGER_DIR = Path(".platformforge/ledgers")

_REQUIRED = ("finding_id", "rule", "case", "root_cause", "regression_test")


@dataclass(frozen=True)
class FalsePositiveRecord:
    finding_id: str = ""
    rule: str = ""
    case: str = ""
    why_false: str = ""
    evidence: tuple[str, ...] = ()
    root_cause: str = ""
    fix: str = ""
    regression_test: str = ""
    status: str = "open"  # open | fixed | wontfix

    def to_dict(self) -> dict[str, Any]:
        return {"schema": "platformforge/fp-record/v1",
                "finding_id": self.finding_id, "rule": self.rule,
                "case": self.case, "why_false": self.why_false,
                "evidence": list(self.evidence),
                "root_cause": self.root_cause, "fix": self.fix,
                "regression_test": self.regression_test,
                "status": self.status}


@dataclass(frozen=True)
class FalseNegativeRecord:
    finding_id: str = ""        # the verdict that should have fired
    rule: str = ""
    case: str = ""
    missed_evidence: str = ""   # what truth was present but unfound
    root_cause: str = ""
    fix: str = ""
    regression_test: str = ""
    status: str = "open"

    def to_dict(self) -> dict[str, Any]:
        return {"schema": "platformforge/fn-record/v1",
                "finding_id": self.finding_id, "rule": self.rule,
                "case": self.case,
                "missed_evidence": self.missed_evidence,
                "root_cause": self.root_cause, "fix": self.fix,
                "regression_test": self.regression_test,
                "status": self.status}


def _errors(d: dict[str, Any], kind: str) -> list[str]:
    errs = [f"missing field: {k}" for k in _REQUIRED if not d.get(k)]
    if d.get("root_cause") and d["root_cause"] not in ROOT_CAUSES:
        errs.append(f"root_cause {d['root_cause']!r} not in {ROOT_CAUSES}")
    if kind == "fp" and not d.get("why_false"):
        errs.append("false-positive record without why_false")
    if kind == "fn" and not d.get("missed_evidence"):
        errs.append("false-negative record without missed_evidence")
    return errs


def record_errors(d: dict[str, Any], kind: str) -> list[str]:
    return _errors(d, kind)


def load_ledger(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    doc = yaml.safe_load(path.read_text()) or {}
    return doc.get("records", [])


def ledger_report(root: str | Path = LEDGER_DIR) -> dict[str, Any]:
    """§66 — confirmed/refuted/unresolved + precision when truth exists."""
    root = Path(root)
    fp = load_ledger(root / "false-positives.yaml")
    fn = load_ledger(root / "false-negatives.yaml")
    errors = []
    for d in fp:
        errors += [f"fp:{d.get('finding_id', '?')}: {e}"
                   for e in _errors(d, "fp")]
    for d in fn:
        errors += [f"fn:{d.get('finding_id', '?')}: {e}"
                   for e in _errors(d, "fn")]
    confirmed = sum(1 for d in fn if d.get("status") == "fixed") + \
        sum(1 for d in fp if d.get("status") == "wontfix")
    refuted = sum(1 for d in fp if d.get("status") == "fixed")
    unresolved = sum(1 for d in fp + fn if d.get("status") == "open")
    # §68 — precision only when a ground-truth corpus exists
    truth = list(Path(".platformforge/cases/golden").glob("*/case.yaml")) + \
        list(Path(".platformforge/cases/holdout").glob("*/case.yaml"))
    precision = None
    if truth:
        # precision = confirmed findings / (confirmed + refuted findings)
        denom = len(fp) + len(fn) or None
        precision = ({"value": None, "note": "no FP/FN records — precision "
                       "unmeasurable without findings to grade"}
                     if denom is None else
                     {"value": round(1 - (len(fp) / denom), 4),
                      "note": "records-based estimate; ground truth = "
                              f"{len(truth)} replay cases"})
    return {"schema": "platformforge/fp-fn-ledger/v1",
            "false_positives": len(fp), "false_negatives": len(fn),
            "confirmed": confirmed, "refuted": refuted,
            "unresolved": unresolved, "precision": precision,
            "errors": errors,
            "verdict": "pass" if not errors else "fail"}


def validate_ledgers(root: str | Path = LEDGER_DIR) -> dict[str, Any]:
    """Gate: every record is well-formed AND its regression_test resolves
    to an existing case.yaml or test file."""
    root = Path(root)
    errors = []
    for kind, f in (("fp", "false-positives.yaml"),
                    ("fn", "false-negatives.yaml")):
        for d in load_ledger(root / f):
            for e in _errors(d, kind):
                errors.append(f"{kind}:{d.get('finding_id', '?')}: {e}")
            rt = d.get("regression_test", "")
            if rt and not _regression_resolves(rt):
                errors.append(f"{kind}:{d.get('finding_id', '?')}: "
                              f"regression_test {rt!r} does not resolve")
    return {"errors": errors, "verdict": "pass" if not errors else "fail"}


def _regression_resolves(ref: str) -> bool:
    """A regression pointer resolves to a case dir, a test file, or a
    scenario dir — never to prose."""
    p = Path(ref)
    if p.exists():
        return True
    for base in (".platformforge/cases/golden", ".platformforge/cases/holdout",
                 "lab/scenarios", "tests"):
        if (Path(base) / ref).exists():
            return True
    return False
