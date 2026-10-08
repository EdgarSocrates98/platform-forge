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
        self.entries: dict[str, SourceEntry] = {}
        self.duplicate_ids: list[str] = []
        for e in doc.get("sources", []):
            if e["id"] in self.entries:
                self.duplicate_ids.append(e["id"])
                continue
            self.entries[e["id"]] = SourceEntry.from_dict(e)

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
        """§46 — report entries missing contract fields, duplicate ids,
        and alias collisions (an alias owned by two entries resolves to
        whichever loads first — silent wrong-linkage)."""
        bad = {}
        for e in self.entries.values():
            missing = [f for f in self.REQUIRED
                       if not getattr(e, f, None)]
            if missing:
                bad[e.id or "?"] = missing
        alias_owner: dict[str, str] = {}
        alias_collisions: dict[str, list[str]] = {}
        for e in self.entries.values():
            for a in e.aliases:
                if a in alias_owner and alias_owner[a] != e.id:
                    alias_collisions.setdefault(a, []).append(e.id)
                else:
                    alias_owner[a] = e.id
        for a, owners in alias_collisions.items():
            owners.insert(0, alias_owner[a])
        ok = not bad and not self.duplicate_ids and not alias_collisions
        return {"entries": len(self.entries), "invalid": bad,
                "duplicate_ids": self.duplicate_ids,
                "alias_collisions": alias_collisions,
                "ok": ok}

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

    def drift_report(self, *catalog_dirs: str | Path,
                     today: date | None = None) -> dict[str, Any]:
        """§47 — knowledge drift: new major versions tracked but not
        reflected, deprecated/superseded sources still cited, unavailable
        sources, and rules whose backing sources went stale.

        Never a bare "ok": every signal carries the entry/rule it
        concerns and the reason."""
        today = today or datetime.now(UTC).date()
        link = self.link_rules(*catalog_dirs)
        statuses = {r["id"]: r for r in self.check(today)}

        signals: list[dict[str, Any]] = []
        for e in sorted(self.entries.values(), key=lambda x: x.id):
            st = statuses.get(e.id, {}).get("status", "unresolved")
            if st in (FreshnessStatus.DEPRECATED,):
                signals.append({"kind": "deprecated-source",
                                "source": e.id,
                                "reason": "entry marked deprecated"})
            if st in (FreshnessStatus.SUPERSEDED,):
                signals.append({"kind": "superseded-source",
                                "source": e.id,
                                "reason": f"superseded_by={e.superseded_by}"})
            if st in (FreshnessStatus.STALE, FreshnessStatus.UNRESOLVED):
                signals.append({"kind": "stale-source", "source": e.id,
                                "reason": f"freshness={st}"})
            if not e.source:
                signals.append({"kind": "unavailable-source",
                                "source": e.id,
                                "reason": "no source locator"})
            # new major version: releases_tracked majors newer than the
            # entry's declared version → knowledge drift signal
            def _maj(v: str) -> int | None:
                import re
                m = re.match(r"\s*v?(\d+)", str(v))
                return int(m.group(1)) if m else None
            cur = _maj(e.version)
            newer = sorted({_maj(r) for r in e.releases_tracked
                            if _maj(r) is not None and cur is not None
                            and _maj(r) > cur})
            for mj in newer:
                signals.append({
                    "kind": "new-major-version", "source": e.id,
                    "reason": f"entry pinned to {e.version} but v{mj} "
                              "is tracked — re-derive version-gated claims"})

        # rules citing stale/deprecated/superseded sources
        stale_ids = {s["source"] for s in signals
                     if s["kind"] in ("deprecated-source",
                                      "superseded-source", "stale-source")}
        stale_rules = [
            {"rule_id": rid, "sources": [s for s in srcs
                                         if s in stale_ids]}
            for rid, srcs in link["linked"].items()
            if any(s in stale_ids for s in srcs)]
        return {"linkage": link,
                "signals": signals,
                "stale_rule_refs": stale_rules,
                "unresolved": [u["rule_id"] for u in link["unlinked"]],
                "counts": {"signals": len(signals),
                           "stale_rules": len(stale_rules),
                           "unlinked": len(link["unlinked"])}}


def knowledge_age_days(retrieved_at: str, today: date | None = None) -> int | None:
    try:
        return ((today or datetime.now(UTC).date()) - date.fromisoformat(str(retrieved_at)[:10])).days
    except ValueError:
        return None


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
