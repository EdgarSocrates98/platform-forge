"""Scenario runner — a scenario is a fixture dir + expected.yaml contract:

    expected:
      analyzers: [iac, k8s]            # verbs to run over fixture/
      violated_rules: [PF-K8S-001]     # must appear
      absent_rules: []                 # must NOT appear
      fact_kinds: [k8s.workload]       # must be produced

Tiers: smoke (one artifact), standard (domain), full (multi-domain).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from platformforge.models import Fact
from platformforge.rules import RuleEngine, load_catalog

_REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIOS_DIR = _REPO_ROOT / "lab" / "scenarios"
CATALOG = _REPO_ROOT / "rules" / "catalog"

_ANALYZERS = {
    "iac": "platformforge.iac.analyze_hcl",
    "k8s": "platformforge.k8s.analyze_k8s",
    "gitops": "platformforge.cicd.analyze_gitops",
    "gha": "platformforge.cicd.analyze_gha",
    "catalog": "platformforge.product.analyze_catalog",
    "crossplane": "platformforge.product.analyze_crossplane",
}


def _resolve(name: str):
    mod, fn = name.rsplit(".", 1)
    import importlib
    return getattr(importlib.import_module(mod), fn)


def list_scenarios() -> list[dict[str, Any]]:
    out = []
    if not SCENARIOS_DIR.is_dir():
        return out
    for d in sorted(SCENARIOS_DIR.iterdir()):
        exp = d / "expected.yaml"
        if d.is_dir() and exp.exists():
            doc = yaml.safe_load(exp.read_text()) or {}
            out.append({"id": d.name, "tier": doc.get("tier", "standard"),
                        "description": doc.get("description", "")})
    return out


def run(scenario_id: str) -> dict[str, Any]:
    d = SCENARIOS_DIR / scenario_id
    exp_path = d / "expected.yaml"
    if not exp_path.exists():
        return {"refusal": "platform.scenario.unresolved",
                "unlock": "platformforge lab list"}
    exp = yaml.safe_load(exp_path.read_text()) or {}
    facts: list[dict[str, Any]] = []
    errors = []
    for dom in exp.get("analyzers", []):
        fn = _resolve(_ANALYZERS[dom])
        try:
            facts += fn(d / "fixture")["facts"]
        except Exception as e:
            errors.append(f"{dom}: {e}")
    rule_facts = [Fact.from_dict(f) for f in facts]
    rules = load_catalog(CATALOG)
    findings, skipped = RuleEngine(rules).evaluate(rule_facts)
    violated = {f.rule_id for f in findings if f.status == "violated"}
    produced_kinds = {f.kind for f in rule_facts}
    want_v = set(exp.get("violated_rules", []))
    want_absent = set(exp.get("absent_rules", []))
    want_kinds = set(exp.get("fact_kinds", []))
    failures = []
    for r in sorted(want_v - violated):
        failures.append(f"expected violated rule missing: {r}")
    for r in sorted(want_absent & violated):
        failures.append(f"rule violated but expected absent: {r}")
    for k in sorted(want_kinds - produced_kinds):
        failures.append(f"expected fact kind missing: {k}")
    return {"scenario": scenario_id, "tier": exp.get("tier", "standard"),
            "passed": not failures and not errors,
            "failures": failures, "analyzer_errors": errors,
            "counts": {"facts": len(rule_facts), "violated": len(violated),
                       "skipped_rules": len(skipped)}}


def run_all() -> dict[str, Any]:
    results = [run(s["id"]) for s in list_scenarios()]
    return {"scenarios": results,
            "passed": sum(1 for r in results if r["passed"]),
            "failed": sum(1 for r in results if not r["passed"])}
