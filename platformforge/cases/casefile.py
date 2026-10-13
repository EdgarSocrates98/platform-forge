"""§54 — case.yaml contract. Fields match the spec's case model;
every record is sanitized before commit (no credentials, identifiers
or confidential payloads)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

SCHEMA = "platformforge/case/v1"
CLASSIFICATIONS = ("synthetic", "fixture-derived", "real-anonymized",
                   "real-live", "production")
TIERS = ("golden", "holdout")
VERDICTS = ("pass", "fail", "unresolved", "expected-fail")
TRUTH_CLASSES = ("known-good", "known-bad", "ambiguous", "partial",
                 "stale", "contradictory")

REQUIRED = ("id", "classification", "tier", "task", "scope",
            "expected_known_truth")


@dataclass(frozen=True)
class CaseFile:
    id: str
    classification: str
    tier: str
    task: str
    scope: str
    truth_class: str = "known-bad"
    analyzers: tuple[str, ...] = ()
    artifacts: tuple[str, ...] = ()
    fixture_from: str = ""
    expected_known_truth: dict[str, Any] = field(default_factory=dict)
    observations: tuple[str, ...] = ()
    agent_route: dict[str, Any] = field(default_factory=dict)
    context_cost: dict[str, Any] = field(default_factory=dict)
    verdict: str = "unresolved"
    path: Path = field(default_factory=Path)

    def to_dict(self) -> dict[str, Any]:
        return {"schema": SCHEMA, "id": self.id,
                "classification": self.classification, "tier": self.tier,
                "task": self.task, "scope": self.scope,
                "truth_class": self.truth_class,
                "analyzers": list(self.analyzers),
                "artifacts": list(self.artifacts),
                "fixture_from": self.fixture_from,
                "expected_known_truth": self.expected_known_truth,
                "observations": list(self.observations),
                "agent_route": self.agent_route,
                "context_cost": self.context_cost,
                "verdict": self.verdict}


def load_case(path: Path) -> CaseFile:
    doc = yaml.safe_load(path.read_text()) or {}
    return CaseFile(
        id=doc.get("id", path.parent.name),
        classification=doc.get("classification", "fixture-derived"),
        tier=doc.get("tier", path.parent.parent.name),
        task=doc.get("task", ""),
        scope=doc.get("scope", ""),
        truth_class=doc.get("truth_class", "known-bad"),
        analyzers=tuple(doc.get("analyzers", [])),
        artifacts=tuple(doc.get("artifacts", [])),
        fixture_from=doc.get("fixture_from", ""),
        expected_known_truth=doc.get("expected_known_truth") or {},
        observations=tuple(doc.get("observations", [])),
        agent_route=doc.get("agent_route") or {},
        context_cost=doc.get("context_cost") or {},
        verdict=doc.get("verdict", "unresolved"),
        path=path,
    )


def case_errors(c: CaseFile) -> list[str]:
    errs = [f"missing field: {k}" for k in REQUIRED if not getattr(c, k, None)]
    if c.classification not in CLASSIFICATIONS:
        errs.append(f"classification {c.classification!r} "
                    f"not in {CLASSIFICATIONS}")
    if c.tier not in TIERS:
        errs.append(f"tier {c.tier!r} not in {TIERS}")
    if c.truth_class not in TRUTH_CLASSES:
        errs.append(f"truth_class {c.truth_class!r} not in {TRUTH_CLASSES}")
    if c.verdict not in VERDICTS:
        errs.append(f"verdict {c.verdict!r} not in {VERDICTS}")
    if not c.analyzers and not c.fixture_from:
        errs.append("case has no analyzers and no fixture_from")
    return errs


def discover_cases(root: str | Path = ".platformforge/cases"
                   ) -> list[CaseFile]:
    root = Path(root)
    out = []
    for tier in TIERS:
        d = root / tier
        if not d.is_dir():
            continue
        for case_dir in sorted(d.iterdir()):
            f = case_dir / "case.yaml"
            if f.exists():
                out.append(load_case(f))
    return out
