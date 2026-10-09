"""Cycle 5 Phase A — analytics contracts (§42–43, §61–63, §243–244,
§249–250).

Invariants:
- `PlatformMetric`: `value` may be absent → reported as `unknown`,
  never coerced to zero (§64, §304);
- every metric carries source + evidence + confidence + completeness
  (§62–63);
- `AnalysisReceipt` makes every aggregate reproducible: same inputs →
  same hash (§243–244);
- `AnalyticsDataQuality` gates confidence — low quality lowers every
  recommendation (§249–251);
- `HistoricalPattern` reports support counts, never causal claims
  (§41–44).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from platformforge.live.models import canonical_hash

METRIC_SCHEMA = "platformforge/metric/v1"
RECEIPT_SCHEMA = "platformforge/analysis-receipt/v1"
PATTERN_SCHEMA = "platformforge/historical-pattern/v1"
DQ_SCHEMA = "platformforge/analytics-data-quality/v1"

CONFIDENCE_LEVELS = ("low", "medium", "high")


@dataclass
class PlatformMetric:
    """§61–63 — one measured value with full provenance."""
    metric_id: str
    dimension: str                    # adoption|reliability|cost|...
    scope: dict[str, str]             # fleet/org/env/team/cluster/…
    value: float | int | str | None = None
    unit: str = ""
    window: str = ""                  # 24h|7d|30d|90d|custom range
    source: str = ""                  # store/ledger/collector id
    evidence: list[str] = field(default_factory=list)
    confidence: str = "low"
    completeness: float | None = None  # 0..1; None when unknown

    def to_dict(self) -> dict[str, Any]:
        d = {"schema": METRIC_SCHEMA, **asdict(self)}
        if self.value is None:
            d["value"] = "unknown"    # §64 — never a fake zero
        return d


@dataclass
class AnalyticsDataQuality:
    """§249–251 — data quality gates analytic confidence."""
    coverage: float | None = None
    freshness: str = "unknown"
    completeness: float | None = None
    consistency: str = "unknown"
    sample_size: int = 0

    @property
    def confidence_cap(self) -> str:
        """§251 — low data quality caps recommendation confidence."""
        if self.sample_size < 3:
            return "low"
        cov = self.coverage if self.coverage is not None else 0.0
        comp = self.completeness if self.completeness is not None else 0.0
        if self.freshness in ("stale", "expired") or cov < 0.8 or comp < 0.8:
            return "low"
        if cov < 1.0 or comp < 1.0 or self.sample_size < 10:
            return "medium"
        return "high"

    def to_dict(self) -> dict[str, Any]:
        return {"schema": DQ_SCHEMA, **asdict(self),
                "confidence_cap": self.confidence_cap}


@dataclass
class AnalysisReceipt:
    """§243 — reproducible aggregate receipt."""
    analysis: str
    scope: dict[str, str]
    window: str = ""
    inputs: list[str] = field(default_factory=list)   # source ids/hashes
    coverage: dict[str, Any] = field(default_factory=dict)
    algorithm: str = ""
    results: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        body = {"schema": RECEIPT_SCHEMA, "analysis": self.analysis,
                "scope": self.scope, "window": self.window,
                "inputs": self.inputs, "coverage": self.coverage,
                "algorithm": self.algorithm, "results": self.results}
        body["hash"] = "sha256:" + canonical_hash(body)
        return body


@dataclass
class HistoricalPattern:
    """§42–44 — recurring pattern with honest support/confidence.
    `hypothesis` names the *possible* explanation; `limitations` keeps
    correlation ≠ causality visible (§41)."""
    pattern_id: str
    window: str
    events: list[str] = field(default_factory=list)
    support: int = 0
    confidence: str = "low"
    evidence: list[str] = field(default_factory=list)
    scope: dict[str, str] = field(default_factory=dict)
    hypothesis: str = ""
    limitations: list[str] = field(default_factory=list)
    sample_size: int = 0              # §233 — recorded, not hidden

    def to_dict(self) -> dict[str, Any]:
        return {"schema": PATTERN_SCHEMA, **asdict(self),
                "causal_claim": False}


def confidence_for_support(n: int) -> str:
    """§232 — 2 occurrences ≠ 200 occurrences."""
    if n < 3:
        return "low"
    if n < 10:
        return "medium"
    return "high"
