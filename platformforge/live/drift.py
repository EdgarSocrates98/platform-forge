"""Live drift — temporal diff between observations (cycle §111–§116).

diff_observations(before, after) emits DriftEvent records:
- resource appeared          → observed-out-of-band candidate evidence
- resource disappeared       → only "deleted" when the AFTER envelope
  is complete+fresh+covering for that type; otherwise unresolved —
  absence needs proof, not just absence of a row (§10, ADR-0013)
- content changed            → drift on whitelisted attr diff

Noise control (§115): identical (resource_id, class, fingerprint)
events dedup per diff; repeated flaps between the same two hashes are
counted, not re-emitted — the event ledger keeps one record with
occurrence count.
"""

from __future__ import annotations

from typing import Any

from platformforge.live.models import DriftEvent, ObservationEnvelope, ObservationScope, canonical_hash

_SAFE_DIFF_ATTRS = None  # all attrs comparable — values were redacted


def _fresh(env: ObservationEnvelope) -> bool:
    return env.freshness_status_at() == "fresh"


def _covers(env: ObservationEnvelope, obj: dict[str, Any]) -> bool:
    scope = ObservationScope.from_dict(env.scope)
    ok, _ = scope.covers({"resource_type": obj.get("resource_type", ""),
                          "namespace": obj.get("namespace", ""),
                          "cluster": obj.get("cluster", ""),
                          "account": obj.get("account", ""),
                          "region": obj.get("region", "")})
    return ok


def _attr_diff(a: dict, b: dict) -> dict[str, Any]:
    keys = set(a) | set(b)
    changed = {k: {"before": a.get(k), "after": b.get(k)}
               for k in sorted(keys) if a.get(k) != b.get(k)}
    return changed


def diff_observations(before: ObservationEnvelope | dict,
                      after: ObservationEnvelope | dict,
                      *, now: str = "") -> dict[str, Any]:
    if isinstance(before, dict):
        before = ObservationEnvelope.from_dict(before)
    if isinstance(after, dict):
        after = ObservationEnvelope.from_dict(after)
    bmap = {o.get("resource_id"): o for o in before.objects}
    amap = {o.get("resource_id"): o for o in after.objects}
    after_fresh = _fresh(after)
    after_complete = (after.coverage or {}).get("status") == "complete"

    events: list[DriftEvent] = []
    unresolved: list[dict[str, Any]] = []

    def _ev(rid: str, cls: str, b: dict, a: dict) -> DriftEvent:
        return DriftEvent(
            drift_id=f"drift-{canonical_hash({'r': rid, 'c': cls, 'a': after.observation_id})[:12]}",
            resource_id=rid, drift_class=cls,
            before={k: v for k, v in b.items()
                    if k in ("attributes", "content_hash", "lifecycle")},
            after={k: v for k, v in a.items()
                   if k in ("attributes", "content_hash", "lifecycle",
                            "diff", "deletion_evidence")},
            observed_at=after.captured_at or now)

    # appeared / changed
    for rid in sorted(amap):
        a, b = amap[rid], bmap.get(rid)
        if b is None:
            events.append(_ev(rid, "observed-out-of-band", {},
                              dict(a, lifecycle="present")))
            continue
        if a.get("content_hash") and a.get("content_hash") == \
                b.get("content_hash"):
            continue
        changed = _attr_diff(b.get("attributes", {}),
                             a.get("attributes", {}))
        if changed:
            events.append(_ev(rid, "config-drift", b,
                              dict(a, diff=changed)))

    # disappeared — needs proof
    for rid in sorted(set(bmap) - set(amap)):
        b = bmap[rid]
        if after_complete and after_fresh and _covers(after, b):
            events.append(_ev(rid, "desired-missing-observed", b,
                              {"lifecycle": "deleted",
                               "deletion_evidence":
                               "absent-in-complete-fresh-snapshot"}))
        else:
            unresolved.append({
                "resource_id": rid,
                "reason": f"after coverage={after.coverage.get('status')} "
                          f"fresh={after_fresh} — deletion unproven",
                "drift_class": "uncomparable"})

    events.sort(key=lambda e: (e.drift_class, e.resource_id))
    return {"drift": [e.to_dict() for e in events],
            "unresolved": unresolved,
            "before": before.observation_id, "after": after.observation_id,
            "window": {"start": before.captured_at,
                       "end": after.captured_at},
            "counts": {c: sum(1 for e in events if e.drift_class == c)
                       for c in sorted({e.drift_class for e in events})},
            "after_complete": after_complete, "after_fresh": after_fresh}


def dedup_events(new: list[dict[str, Any]],
                 prior: list[dict[str, Any]]) -> tuple[list[dict], int]:
    """§115 — drop events identical to previously journaled ones
    (same resource+class+after-hash); return (kept, suppressed)."""
    seen = {(e.get("resource_id"), e.get("drift_class"),
             (e.get("after") or {}).get("content_hash"))
            for e in prior}
    kept, suppressed = [], 0
    for e in new:
        key = (e.get("resource_id"), e.get("drift_class"),
               (e.get("after") or {}).get("content_hash"))
        if key in seen:
            suppressed += 1
        else:
            kept.append(e)
            seen.add(key)
    return kept, suppressed
