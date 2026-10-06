"""Canonical contracts for the epistemic pipeline.

Fact:      something directly observed (anchored, tiered, provenanced).
Finding:   a judgment over facts — invalid without non-empty evidence.
Refusal:   a named "we cannot tell" — never "probably".
Recommendation: judgment + context, carries its epistemic basis.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from enum import IntEnum
from typing import Any


class EvidenceTier(IntEnum):
    """Authority ordering. T6/T7 never silently become facts."""

    MEASURED_RUNTIME = 0
    PROVIDER_OBSERVED = 1
    GENERATED_PLAN = 2
    REPO_CONFIG = 3
    OFFICIAL_DOC = 4
    OPERATOR_DECLARED = 5
    LLM_INFERENCE = 6
    CONJECTURE = 7

    @property
    def label(self) -> str:
        return {
            0: "measured-runtime",
            1: "provider-observed",
            2: "generated-plan",
            3: "repo-config",
            4: "official-doc",
            5: "operator-declared",
            6: "llm-inference",
            7: "conjecture",
        }[int(self)]


class FreshnessStatus(str):
    CURRENT = "current"
    FRESH = "fresh"
    STALE = "stale"
    DEPRECATED = "deprecated"
    SUPERSEDED = "superseded"
    CONFLICTED = "conflicted"
    UNRESOLVED = "unresolved"


class RefusalCode:
    """Named refusals — evidence gaps are data, never hedged prose."""

    COST = "platform.cost.unresolved"
    NETWORK = "platform.network.unresolved"
    IDENTITY = "platform.identity.unresolved"
    RUNTIME = "platform.runtime.unresolved"
    VERSION = "platform.version.unresolved"
    TOPOLOGY = "platform.topology.unresolved"
    SLO = "platform.slo.unresolved"
    OWNERSHIP = "platform.ownership.unresolved"
    SECURITY = "platform.security.unresolved"
    EVIDENCE = "platform.evidence.unresolved"

    ALL = (
        COST, NETWORK, IDENTITY, RUNTIME, VERSION, TOPOLOGY, SLO, OWNERSHIP, SECURITY, EVIDENCE
    )


FACT_ID_RE = re.compile(r"^PF-[A-Z0-9]+-[0-9]+$")
FINDING_ID_RE = re.compile(r"^PF-F-[0-9]+$")
RULE_ID_RE = re.compile(r"^PF-[A-Z0-9]+(-[A-Z0-9]+)*-[0-9]+$")


def stable_id(prefix: str, *parts: str) -> str:
    """Deterministic numeric id derived from content — stable across runs
    given identical inputs, so findings can cite fact_ids durably."""
    digest = hashlib.sha256("\x00".join(parts).encode()).hexdigest()
    return f"{prefix}-{int(digest[:12], 16) % 10**12:012d}"


@dataclass
class Fact:
    kind: str
    source: str
    location: str
    tier: int = EvidenceTier.REPO_CONFIG
    observed: bool = True
    attrs: dict[str, Any] = field(default_factory=dict)
    measures: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)
    freshness: dict[str, Any] = field(default_factory=dict)
    fact_id: str = ""

    def __post_init__(self) -> None:
        if int(self.tier) >= EvidenceTier.LLM_INFERENCE:
            raise ValueError(f"T6/T7 evidence cannot become a Fact (tier={self.tier})")
        if not self.fact_id:
            self.fact_id = stable_id(
                "PF-" + self.domain_prefix,
                self.kind, self.location,
                json.dumps(self.attrs, sort_keys=True, default=str),
            )
        if not FACT_ID_RE.match(self.fact_id):
            raise ValueError(f"invalid fact_id: {self.fact_id}")

    @property
    def domain_prefix(self) -> str:
        """PF-<KIND AREA>-<n>: area derived from kind (`k8s.workload` -> K8S)."""
        return self.kind.split(".")[0].upper().replace("_", "-") or "GEN"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["tier"] = int(self.tier)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Fact":
        return cls(**d)


@dataclass
class Finding:
    """A judgment over facts. Empty evidence is invalid by construction."""

    rule_id: str
    severity: str
    status: str  # violated | passed | unresolved | not-applicable
    evidence: list[str]
    finding_id: str = ""
    title: str = ""
    message: str = ""
    location: str = ""
    attrs: dict[str, Any] = field(default_factory=dict)

    SEVERITIES = ("info", "low", "medium", "high", "critical")
    STATUSES = ("violated", "passed", "unresolved", "not-applicable")

    def __post_init__(self) -> None:
        if self.status == "violated" and not self.evidence:
            raise ValueError(f"finding {self.rule_id}: violated requires non-empty evidence")
        if self.severity not in self.SEVERITIES:
            raise ValueError(f"invalid severity: {self.severity}")
        if self.status not in self.STATUSES:
            raise ValueError(f"invalid status: {self.status}")
        if not RULE_ID_RE.match(self.rule_id):
            raise ValueError(f"invalid rule_id: {self.rule_id}")
        if not self.finding_id:
            self.finding_id = stable_id(
                "PF-F", self.rule_id, ",".join(sorted(self.evidence)), self.message
            )
        if not FINDING_ID_RE.match(self.finding_id):
            raise ValueError(f"invalid finding_id: {self.finding_id}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Refusal:
    code: str
    field: str
    unlock: str
    message: str = ""
    missing_evidence: list[str] = field(default_factory=list)
    refusal_id: str = ""

    def __post_init__(self) -> None:
        if not self.refusal_id:
            self.refusal_id = stable_id("PF-R", self.code, self.field)
        if not (self.code.endswith(".unresolved") or RULE_ID_RE.match(self.code)):
            raise ValueError(f"invalid refusal code: {self.code}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Recommendation:
    """Judgment + context. Always exposes its epistemic basis."""

    title: str
    severity: str
    confidence: str
    evidence: list[str]
    proposed_change: list[str]
    risks: list[str]
    validation: list[str]
    rollback: list[str]
    basis: dict[str, list[str]]  # observed | declared | inferred | unknown
    root_cause: str | None = None
    expected_effect: str | None = None
    benchmark_ref: str | None = None
    tradeoffs: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.evidence:
            raise ValueError("recommendation requires evidence — never invent it")
        if self.expected_effect and any(
            ch.isdigit() for ch in self.expected_effect
        ) and not self.benchmark_ref:
            raise ValueError(
                "quantified expected_effect requires benchmark_ref — "
                "an unmeasured gain claim is an invention"
            )
        for k in ("observed", "declared", "inferred", "unknown"):
            self.basis.setdefault(k, [])

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
