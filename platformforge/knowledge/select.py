"""Knowledge economy (§208–215) — load only the relevant packs.

Selector inputs: task, domain, version, risk (§209). A pack declares
applicability (`applies_to`); PackApplicability is the verdict (§210).
Pack budget caps how many packs a task loads — never the whole registry
(§211). Stale packs are flagged `review_needed`, not silently trusted
(§212). Search tiers are lexical/graph — no embeddings required (§213–214).
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class PackApplicability:
    """§210 — why a pack does or doesn't apply to a task."""
    pack_id: str
    applicable: bool
    reason: str
    freshness: str = "unknown"       # current|stale|unresolved
    score: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def select_packs(packs: list[Any], *, domain: str = "",
                 versions: dict[str, str] | None = None,
                 risk: str = "low", max_packs: int = 8,
                 freshness_of=None) -> dict[str, Any]:
    """§209–212 — select applicable packs within budget.

    `packs` are knowledge.packs.Pack-like objects exposing
    `pack_id/domain/applies_to/claims`. `freshness_of` maps a pack's
    source ids to a freshness state (defaults: unknown → review_needed
    for high risk).
    """
    versions = versions or {}
    verdicts: list[PackApplicability] = []
    for p in packs:
        score, reasons = 0, []
        if domain and getattr(p, "domain", "") == domain:
            score += 2
            reasons.append("domain match")
        applies = getattr(p, "applies_to", {}) or {}
        ok_versions = True
        for prod, want in (applies.get("versions") or {}).items():
            # applies_to.versions lists products the pack covers; the
            # task's detected version for that product decides fit.
            want = str(want)
            have = versions.get(prod, "")
            if prod in versions and _version_ok(have, want):
                score += 2
                reasons.append(f"{prod} {have} matches {want}")
            elif prod not in versions:
                pass                       # pack covers more than needed
        if domain and getattr(p, "domain", "") and \
                p.domain != domain:
            ok_versions = False
            reasons.append("domain mismatch")
        verdicts.append(PackApplicability(
            pack_id=getattr(p, "pack_id", "?"),
            applicable=ok_versions and score > 0,
            reason="; ".join(reasons) or "no applicability signal",
            score=score))

    applicable = sorted((v for v in verdicts if v.applicable),
                        key=lambda v: -v.score)
    selected: list[PackApplicability] = []
    for v in applicable[:max_packs]:
        fr = freshness_of(v.pack_id) if freshness_of else "unknown"
        v.freshness = fr
        if fr in ("stale", "unresolved") and risk in ("high", "critical"):
            v.reason += "; review_needed (stale pack under high risk)"
        selected.append(v)
    return {"selected": [v.to_dict() for v in selected],
            "skipped": [v.to_dict() for v in verdicts
                        if not v.applicable],
            "budget": max_packs,
            "overflow": max(0, len(applicable) - max_packs)}


def _version_ok(have: str, want: str) -> bool:
    """Minimal semver-ish range check (>=X.Y, >X.Y, ==X.Y, bare prefix)."""
    m = re.match(r"^\s*(>=|>|<=|<|==)?\s*([\d.]+)", want)
    if not m:
        return have == want
    op, target = m.groups()
    h = [int(x) for x in have.split(".") if x.isdigit()]
    t = [int(x) for x in target.split(".") if x.isdigit()]
    n = max(len(h), len(t))
    h += [0] * (n - len(h)); t += [0] * (n - len(t))
    if op in (None, "=="):
        return h == t
    if op == ">=":
        return h >= t
    if op == ">":
        return h > t
    if op == "<=":
        return h <= t
    return h < t


def search_knowledge(packs: list[Any], query: str,
                     *, tier2_graph=None) -> dict[str, Any]:
    """§213–214 — tiered search, no embeddings.

    Tier 0: exact id/ref match. Tier 1: lexical substring/FTS over pack
    id+domain+claims. Tier 2: caller-supplied graph expansion hook."""
    q = query.lower()
    t0 = [p for p in packs if getattr(p, "pack_id", "") == query]
    if t0:
        return {"tier": 0, "packs": t0}
    t1 = [p for p in packs if q in getattr(p, "pack_id", "").lower()
          or q in getattr(p, "domain", "").lower()
          or any(q in c.statement.lower()
                 for c in getattr(p, "claims", ()))]
    if t1:
        return {"tier": 1, "packs": t1}
    if tier2_graph is not None:
        expanded = tier2_graph(query)
        return {"tier": 2, "packs": expanded}
    return {"tier": 2, "packs": [], "note": "no lexical match; "
            "tier-2 graph expansion unavailable"}
