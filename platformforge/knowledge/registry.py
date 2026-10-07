"""Source registry + knowledge freshness.

Old documentation is never eternal truth. Every version-dependent claim cites
a source entry; freshness is computed, not assumed.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

UTC = timezone.utc  # datetime.UTC alias is 3.11+; keep 3.10 compatible
from pathlib import Path
from typing import Any

import yaml

from platformforge.models import FreshnessStatus

FRESH_DAYS = 120       # verified within ~4 months
STALE_DAYS = 365       # older than a year → stale by default

# Closed vocabulary for `source_authority` — asserted by the CI gate.
SOURCE_AUTHORITIES = ("official", "vendor-research", "first-party-sibling")


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
    aliases: list[str] = field(default_factory=list)

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
        from platformforge.resources import data_path
        return cls(data_path("knowledge", "sources.yaml"))

    def get(self, source_id: str) -> SourceEntry | None:
        return self.entries.get(source_id)

    def resolve(self, ref: str) -> SourceEntry | None:
        """Canonical id, else explicit `aliases:` declared on an entry.
        No inference — a ref that is neither is unresolvable."""
        if ref in self.entries:
            return self.entries[ref]
        for e in self.entries.values():
            if ref in e.aliases:
                return e
        return None

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


    # §46 — knowledge entry contract: these fields are mandatory for an
    # entry to count as knowledge-backed.
    REQUIRED = ("id", "source", "source_authority", "retrieved_at",
                "confidence")

    def contract_check(self) -> dict[str, Any]:
        """§46 — report entries missing contract fields."""
        bad = {}
        for e in self.entries.values():
            missing = [f for f in self.REQUIRED
                       if not getattr(e, f, None)]
            if missing:
                bad[e.id or "?"] = missing
        return {"entries": len(self.entries), "invalid": bad,
                "ok": not bad}

    def link_rules(self, *catalog_dirs: str | Path) -> dict[str, Any]:
        """§44/§47 + cycle 2.1 — rule→source linkage by exact canonical id.

        Every `sources:` entry on a rule must be a registered id (or an
        entry's explicit `aliases:` member). No domain-suffix inference —
        `k8s.io` must never silently match `gateway-api.sigs.k8s.io`.
        Unresolvable refs are reported `unlinked`, not silently trusted.
        """
        from platformforge.rules import load_catalog
        linked, unlinked, bad_refs = {}, [], []
        for r in load_catalog(*catalog_dirs):
            hits = [{"source": s,
                     "entry": (self.resolve(s) or SourceEntry(
                         id="", source="")).id or None}
                    for s in r.sources]
            if hits and all(h["entry"] for h in hits):
                linked[r.rule_id] = [h["entry"] for h in hits]
            else:
                unlinked.append({"rule_id": r.rule_id, "sources": hits})
            dangling = sorted(k for k in getattr(r, "source_refs", {})
                              if k not in r.sources)
            if dangling:
                bad_refs.append({"rule_id": r.rule_id,
                                 "source_refs": dangling})
        return {"linked": linked, "unlinked": unlinked, "bad_refs": bad_refs,
                "coverage": len(linked) / max(len(linked) + len(unlinked), 1)}


def knowledge_age_days(retrieved_at: str, today: date | None = None) -> int | None:
    try:
        return ((today or datetime.now(UTC).date()) - date.fromisoformat(str(retrieved_at)[:10])).days
    except ValueError:
        return None


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
