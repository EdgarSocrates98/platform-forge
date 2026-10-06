"""Executable rules over facts.

A rule = applicability + conditions over fact attrs. Conditions support a
closed operator vocabulary; anything unparseable fails loudly at catalog load,
not silently at judge time.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from platformforge.models import Fact, Finding

OPS = {
    "absent", "present", "equals", "not_equals", "gt", "gte", "lt", "lte",
    "contains", "not_contains", "matches", "in", "empty", "not_empty",
}


def _parse_version(v: str) -> tuple[int, ...]:
    parts = re.findall(r"\d+", str(v))
    return tuple(int(p) for p in parts) if parts else ()


def version_satisfies(version: str | None, constraint: str | None) -> bool | None:
    """True/False when decidable, None when version unknown."""
    if not constraint:
        return True
    if not version:
        return None
    have = _parse_version(version)
    if not have:
        return None
    for cond in str(constraint).split():
        m = re.match(r"(>=|<=|==|!=|>|<)?\s*(.+)", cond)
        if not m:
            continue
        op, want_s = m.group(1) or "==", m.group(2)
        want = _parse_version(want_s)
        n = max(len(have), len(want))
        a, b = have + (0,) * (n - len(have)), want + (0,) * (n - len(want))
        ok = {
            "==": a == b, "!=": a != b, ">=": a >= b,
            "<=": a <= b, ">": a > b, "<": a < b,
        }[op]
        if not ok:
            return False
    return True


def _values_at(obj: Any, path: str) -> list[Any]:
    """Resolve `a.b[*].c` over dicts/lists → list of candidate values.
    Missing keys yield [MISSING]."""
    nodes = [obj]
    for part in path.split("."):
        nxt: list[Any] = []
        many = part.endswith("[*]")
        key = part[:-3] if many else part
        for node in nodes:
            if isinstance(node, dict):
                node = node.get(key, MISSING)
            else:
                node = MISSING
            if many and isinstance(node, list):
                nxt.extend(node)
            else:
                nxt.append(node)
        nodes = nxt
    return nodes


class _Missing:
    def __repr__(self) -> str:  # pragma: no cover
        return "<missing>"


MISSING = _Missing()


def _eval_op(value: Any, op: str, expected: Any = None) -> bool:
    if op == "absent":
        return value is MISSING or value is None
    if op == "present":
        return value is not MISSING and value is not None
    if value is MISSING:
        return False
    if op == "equals":
        return value == expected
    if op == "not_equals":
        return value != expected
    if op == "gt":
        return _num(value) is not None and _num(value) > _num(expected)
    if op == "gte":
        return _num(value) is not None and _num(value) >= _num(expected)
    if op == "lt":
        return _num(value) is not None and _num(value) < _num(expected)
    if op == "lte":
        return _num(value) is not None and _num(value) <= _num(expected)
    if op == "contains":
        return expected in value if isinstance(value, (list, dict, str)) else False
    if op == "not_contains":
        return expected not in value if isinstance(value, (list, dict, str)) else True
    if op == "matches":
        return bool(re.search(str(expected), str(value)))
    if op == "in":
        return value in (expected or [])
    if op == "empty":
        return value in ("", [], {}, None)
    if op == "not_empty":
        return value not in ("", [], {}, None)
    raise ValueError(f"unknown op: {op}")


def _num(v: Any) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


@dataclass
class Rule:
    rule_id: str
    title: str
    domain: str
    severity: str
    conditions: dict[str, Any]          # {"all": [...], "any": [...], "none": [...]}
    applies_to: dict[str, Any] = field(default_factory=dict)  # {fact_kind: ...}
    versions: dict[str, str] = field(default_factory=dict)
    scope: str = "fact"                 # fact | aggregate
    evidence_requirements: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    action: dict[str, Any] = field(default_factory=dict)
    message: str = ""
    enabled: bool = True

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Rule:
        conds = d.get("conditions", {})
        for group in ("all", "any", "none"):
            for pred in conds.get(group, []) or []:
                if pred.get("op") not in OPS:
                    raise ValueError(
                        f"{d.get('rule_id')}: unknown op {pred.get('op')!r} "
                        f"(allowed: {sorted(OPS)})"
                    )
        return cls(
            rule_id=d["rule_id"], title=d.get("title", ""), domain=d.get("domain", ""),
            severity=d.get("severity", "medium"), conditions=conds,
            applies_to=d.get("applies_to", {}), versions=d.get("versions", {}),
            scope=d.get("scope", "fact"),
            evidence_requirements=d.get("evidence_requirements", []),
            sources=d.get("sources", []), action=d.get("action", {}),
            message=d.get("message", ""), enabled=d.get("enabled", True),
        )


def load_catalog(*dirs: str | Path) -> list[Rule]:
    """Load all rule YAML files from catalog dirs (sorted → deterministic)."""
    rules: list[Rule] = []
    for d in dirs:
        p = Path(d)
        if not p.is_dir():
            continue
        for f in sorted(p.rglob("*.yaml")) + sorted(p.rglob("*.yml")):
            doc = yaml.safe_load(f.read_text()) or {}
            for entry in doc.get("rules", doc if isinstance(doc, list) else []):
                rules.append(Rule.from_dict(entry))
    return rules


class RuleEngine:
    def __init__(self, rules: Iterable[Rule], versions: dict[str, str] | None = None):
        self.rules = [r for r in rules if r.enabled]
        self.versions = versions or {}

    def _version_gate(self, rule: Rule) -> tuple[bool, list[str]]:
        """(applies, unresolved_notes). Unknown versions mark unresolved,
        never silently skip."""
        notes = []
        for product, constraint in rule.versions.items():
            sat = version_satisfies(self.versions.get(product), constraint)
            if sat is False:
                return False, notes
            if sat is None:
                notes.append(f"platform.version.unresolved:{product}({constraint})")
        return True, notes

    def _eval_predicates(self, fact: Fact, conds: dict[str, Any]) -> bool:
        doc = {"kind": fact.kind, "source": fact.source, "location": fact.location,
               "tier": int(fact.tier), "observed": fact.observed,
               "attrs": fact.attrs, "measures": fact.measures}

        def pred_ok(p: dict[str, Any]) -> bool:
            values = _values_at(doc, p["path"])
            # quantifier: exists (default) — any candidate satisfies
            if p.get("quantifier") == "for_all":
                return bool(values) and all(
                    _eval_op(v, p["op"], p.get("value")) for v in values)
            return any(_eval_op(v, p["op"], p.get("value")) for v in values)

        all_ok = all(pred_ok(p) for p in conds.get("all", []) or [])
        any_list = conds.get("any", []) or []
        any_ok = (any(pred_ok(p) for p in any_list)) if any_list else True
        none_ok = not any(pred_ok(p) for p in conds.get("none", []) or [])
        return all_ok and any_ok and none_ok

    def evaluate(self, facts: list[Fact]) -> tuple[list[Finding], list[dict[str, Any]]]:
        """→ (findings, skipped) — skipped rules carry reason, not silence."""
        findings: list[Finding] = []
        skipped: list[dict[str, Any]] = []
        for rule in self.rules:
            ok, notes = self._version_gate(rule)
            if not ok:
                skipped.append({"rule_id": rule.rule_id, "reason": "version-mismatch"})
                continue
            if rule.scope == "aggregate":
                skipped.append({"rule_id": rule.rule_id,
                                "reason": "aggregate-scope-not-implemented"})
                continue
            kind = rule.applies_to.get("fact_kind")
            targets = [f for f in facts if f.kind == kind] if kind else facts
            if kind and not targets:
                skipped.append({"rule_id": rule.rule_id,
                                "reason": f"no facts of kind {kind}"})
            for fact in targets:
                violated = self._eval_predicates(fact, rule.conditions)
                status = "violated" if violated else "passed"
                attrs = dict(rule.action)
                if notes:
                    attrs["version_notes"] = notes
                findings.append(Finding(
                    rule_id=rule.rule_id, severity=rule.severity, status=status,
                    evidence=[fact.fact_id], title=rule.title,
                    message=rule.message or rule.title,
                    location=fact.location, attrs=attrs,
                ))
        return findings, skipped
