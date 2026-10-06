"""Source registry + knowledge freshness.

Old documentation is never eternal truth. Every version-dependent claim cites
a source entry; freshness is computed, not assumed.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import yaml

from platformforge.models import FreshnessStatus

FRESH_DAYS = 120       # verified within ~4 months
STALE_DAYS = 365       # older than a year → stale by default


@dataclass
class SourceEntry:
    id: str
    source: str
    source_authority: str = "unknown"
    retrieved_at: str = ""
    product: str = ""
    version: str = ""
    releases_tracked: list[str] = field(default_factory=list)
    scope: str = ""
    cloud: str = ""
    deprecated: bool = False
    superseded_by: str = ""
    valid_from: str = ""
    valid_until: str = ""
    confidence: str = "medium"
    notes: str = ""

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SourceEntry:
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in known})

    def freshness(self, today: date | None = None) -> str:
        """current|fresh|stale|deprecated|superseded|conflicted|unresolved."""
        today = today or datetime.now(UTC).date()
        if self.deprecated:
            return FreshnessStatus.DEPRECATED
        if self.superseded_by:
            return FreshnessStatus.SUPERSEDED
        if self.valid_until and str(self.valid_until) < today.isoformat():
            return FreshnessStatus.STALE
        if self.valid_from and str(self.valid_from) > today.isoformat():
            return FreshnessStatus.UNRESOLVED
        if not self.retrieved_at:
            return FreshnessStatus.UNRESOLVED
        try:
            days = (today - date.fromisoformat(str(self.retrieved_at)[:10])).days
        except ValueError:
            return FreshnessStatus.UNRESOLVED
        if days <= FRESH_DAYS:
            return FreshnessStatus.CURRENT if days <= 30 else FreshnessStatus.FRESH
        return FreshnessStatus.STALE if days > STALE_DAYS else FreshnessStatus.FRESH


class SourceRegistry:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        doc = yaml.safe_load(self.path.read_text())
        self.schema = doc.get("schema", "")
        self.entries: dict[str, SourceEntry] = {
            e["id"]: SourceEntry.from_dict(e) for e in doc.get("sources", [])
        }

    @classmethod
    def default(cls) -> SourceRegistry:
        return cls(Path(__file__).resolve().parents[2] / "knowledge" / "sources.yaml")

    def get(self, source_id: str) -> SourceEntry | None:
        return self.entries.get(source_id)

    def check(self, today: date | None = None) -> list[dict[str, Any]]:
        """Freshness report for every registered source."""
        return [
            {"id": e.id, "product": e.product, "version": e.version,
             "retrieved_at": e.retrieved_at, "status": e.freshness(today),
             "superseded_by": e.superseded_by}
            for e in sorted(self.entries.values(), key=lambda x: x.id)
        ]

    def unresolved(self, today: date | None = None) -> list[str]:
        return [r["id"] for r in self.check(today) if r["status"] in
                (FreshnessStatus.UNRESOLVED, FreshnessStatus.CONFLICTED)]


def knowledge_age_days(retrieved_at: str, today: date | None = None) -> int | None:
    try:
        return ((today or datetime.now(UTC).date()) - date.fromisoformat(str(retrieved_at)[:10])).days
    except ValueError:
        return None


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
