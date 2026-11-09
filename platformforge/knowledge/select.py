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
    state: str = "unknown"           # applicable|not_applicable|unknown|requires_review

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
        state = "unknown"
        if domain and getattr(p, "domain", "") == domain:
            score += 2
            reasons.append("domain match")
            state = "applicable"
        applies = getattr(p, "applies_to", {}) or {}
        version_states: list[str] = []
        for prod, want in (applies.get("versions") or {}).items():
            # applies_to.versions lists products the pack covers; the
            # task's detected version for that product decides fit.
            want = str(want)
            have = versions.get(prod, "")
            if not have or have.lower() in {"unknown", "n/a", "none"}:
                version_states.append("requires_review")
                reasons.append(f"{prod} version missing")
            elif _version_ok(have, want):
                score += 2
                reasons.append(f"{prod} {have} matches {want}")
            else:
                version_states.append("not_applicable")
                reasons.append(f"{prod} {have} does not match {want}")
        # An explicit incompatibility is stronger than an unresolved second
        # requirement.  Otherwise a pack requiring, for example, Kubernetes
        # 1.30 *and* an unknown runtime could be downgraded to
        # ``requires_review`` and accidentally look selectable later.
        if "not_applicable" in version_states:
            version_state = "not_applicable"
        elif "requires_review" in version_states:
            version_state = "requires_review"
        else:
            version_state = "applicable"
        if domain and getattr(p, "domain", "") and \
                p.domain != domain:
            state = "not_applicable"
            reasons.append("domain mismatch")
        elif version_state == "not_applicable":
            state = "not_applicable"
        elif version_state == "requires_review":
            state = "requires_review"
        elif score > 0:
            state = "applicable"
        else:
            state = "unknown"
        verdicts.append(PackApplicability(
            pack_id=getattr(p, "pack_id", "?"),
            applicable=state == "applicable" and score > 0,
            reason="; ".join(reasons) or "no applicability signal",
            score=score, state=state))

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
    """Small semver range evaluator with explicit prerelease ordering.

    It intentionally supports only declarative constraints used by packs:
    comma-separated comparators, ``^`` and ``~``. Unknown syntax fails closed.
    """
    observed = _parse_version(have)
    if observed is None:
        return False
    alternatives = [part.strip() for part in want.split("||") if part.strip()]
    return any(_range_ok(observed, part) for part in alternatives)


def _parse_version(value: str) -> tuple[tuple[int, int, int], tuple[str, ...]] | None:
    match = re.fullmatch(r"\s*[v=]?([0-9]+)(?:\.([0-9]+))?(?:\.([0-9]+))?(?:-([0-9A-Za-z.-]+))?\s*", value)
    if not match:
        return None
    major, minor, patch, pre = match.groups()
    return ((int(major), int(minor or 0), int(patch or 0)),
            tuple(pre.split(".")) if pre else ())


def _compare_version(left, right) -> int:
    if left[0] != right[0]:
        return (left[0] > right[0]) - (left[0] < right[0])
    if not left[1] and right[1]:
        return 1
    if left[1] and not right[1]:
        return -1
    for a, b in zip(left[1], right[1]):
        if a == b:
            continue
        if a.isdigit() and b.isdigit():
            return (int(a) > int(b)) - (int(a) < int(b))
        if a.isdigit() != b.isdigit():
            return -1 if a.isdigit() else 1
        return (a > b) - (a < b)
    return (len(left[1]) > len(right[1])) - (len(left[1]) < len(right[1]))


def _range_ok(observed, requirement: str) -> bool:
    checks = [part.strip() for part in requirement.split(",") if part.strip()]
    if not checks:
        return False
    for check in checks:
        match = re.fullmatch(r"(\^|~|>=|<=|>|<|==|=)?\s*(.+)", check)
        if not match:
            return False
        op, raw_target = match.groups()
        target = _parse_version(raw_target)
        if target is None:
            return False
        cmp = _compare_version(observed, target)
        if op in (None, "=", "==") and cmp != 0:
            return False
        if op == ">=" and cmp < 0:
            return False
        if op == ">" and cmp <= 0:
            return False
        if op == "<=" and cmp > 0:
            return False
        if op == "<" and cmp >= 0:
            return False
        if op == "~" and (
            cmp < 0
            or (observed[0][0], observed[0][1]) != (target[0][0], target[0][1])
        ):
            return False
        if op == "^" and (cmp < 0 or not _caret_upper_bound_ok(observed, target)):
            return False
    return True


def _caret_upper_bound_ok(observed, target) -> bool:
    """Apply npm-style semver caret bounds, including ``0.x`` packages.

    ``^1.2.3`` means ``<2.0.0``; ``^0.2.3`` means ``<0.3.0`` and
    ``^0.0.3`` means ``<0.0.4``.  A major-only comparison is unsafe for
    pre-1.0 runtimes because minor releases can contain breaking changes.
    """
    major, minor, patch = target[0]
    if major > 0:
        upper = ((major + 1, 0, 0), ())
    elif minor > 0:
        upper = ((0, minor + 1, 0), ())
    else:
        upper = ((0, 0, patch + 1), ())
    return _compare_version(observed, upper) < 0


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
