"""Reconciliation engine (cycle §100–§110).

Compares DESIRED ↔ PLANNED ↔ OBSERVED ↔ RUNTIME layers and emits
structured DriftEvent records — never a bare boolean, never silently
resolved contradictions.

Governing rules:
- §103 — temporally incompatible snapshots degrade every affected
  comparison to `stale-observation`/`uncomparable`; they are NOT
  compared as if simultaneous.
- §10/ADR-0013 — a "missing" verdict requires complete+fresh+covering
  observation; otherwise `permission-unknown`/`scope-mismatch`/
  `unresolved` wins over `desired-missing-observed`.
- §108 — accepted drift is declared input, recorded, not hidden.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from platformforge.live.models import (
    DRIFT_CLASSES,
    DriftEvent,
    ObservationEnvelope,
    ObservationScope,
    canonical_hash,
    now_iso,
)

# drift classes that mean "different content" and map onto semantic
# attr categories (shared vocabulary with graph/diff.py categories)
_ATTR_CLASS_HINTS = {
    "identity": "identity-drift", "network": "network-drift",
    "exposure": "security-drift", "security": "security-drift",
    "policy": "policy-drift", "runtime": "version-drift",
    "region": "scope-mismatch", "slo": "config-drift",
    "cost": "config-drift", "ha": "config-drift",
    "storage": "config-drift", "supply_chain": "config-drift",
    "ownership": "config-drift", "replication": "config-drift",
    "deployment": "version-drift"}
_ATTR_TO_CATEGORY = {
    "identity": ("principal", "role", "policy", "service_account",
                 "identity", "assume", "permissions", "role_arn"),
    "network": ("cidr", "port", "protocol", "subnet", "vpc", "route",
                "gateway", "dns", "peer"),
    "exposure": ("public", "expose", "ingress", "external", "tls",
                 "listener", "anonymous"),
    "runtime": ("image", "runtime", "version", "tag", "digest",
                "command", "args", "env"),
    "security": ("encryption", "kms", "public_access", "acl",
                 "secret"),
    "policy": ("policy", "compliance", "tag_policy"),
    "region": ("region", "location")}


@dataclass
class CompareInput:
    """Normalized resource records from any layer."""
    layer: str                                   # desired|planned|observed|runtime
    resources: dict[str, dict[str, Any]] = field(default_factory=dict)
    timestamp: str = ""
    coverage: str = "unknown"                    # observed only
    scope: dict[str, Any] = field(default_factory=dict)
    fresh: bool = True


def _keys_of(res: dict[str, Any]) -> set[str]:
    """Candidate match keys — strong first, weak triple as fallback."""
    keys = set()
    attrs = res.get("attrs") or res.get("attributes") or {}
    for k in ("arn", "uid", "resource_id", "canonical_id",
              "terraform_address"):
        v = attrs.get(k) or res.get(k)
        if v:
            keys.add(str(v))
    rid = res.get("resource_id") or res.get("location") or ""
    if rid:
        keys.add(str(rid))
    kind = res.get("resource_type") or res.get("kind", "")
    ns = res.get("namespace", "") or attrs.get("namespace", "")
    name = res.get("name", "") or attrs.get("name", "")
    if kind and name:
        keys.add(f"{kind}:{ns}:{name}")
    return keys


def norm_facts(facts: list[dict[str, Any]], layer: str,
               timestamp: str = "") -> CompareInput:
    """Desired/planned facts → CompareInput keyed by first strong key."""
    inp = CompareInput(layer=layer, timestamp=timestamp)
    for f in facts:
        res = {"resource_id": f.get("location", "") or f.get("fact_id", ""),
               "resource_type": f.get("kind", ""),
               "attrs": f.get("attrs", {}), "fact_ids": [f.get("fact_id", "")]}
        for k in _keys_of(res):
            inp.resources.setdefault(k, res)
    return inp


def norm_observed(env: ObservationEnvelope | dict[str, Any],
                  at=None) -> CompareInput:
    """Observation envelope → CompareInput carrying coverage/freshness."""
    if isinstance(env, dict):
        env = ObservationEnvelope.from_dict(env)
    inp = CompareInput(layer="observed", timestamp=env.captured_at,
                       coverage=(env.coverage or {}).get("status",
                                                         "unknown"),
                       scope=env.scope or {})
    for o in env.objects:
        res = dict(o)
        res["attrs"] = o.get("attributes", {})
        for k in _keys_of(res):
            inp.resources.setdefault(k, res)
    inp.fresh = env.freshness_status_at(at) == "fresh"
    return inp


def norm_runtime_edges(graph=None, edges: list[dict] | None = None,
                       timestamp: str = "") -> CompareInput:
    """Runtime edges/objects → CompareInput (undeclared detection)."""
    inp = CompareInput(layer="runtime", timestamp=timestamp)
    for e in edges or []:
        rid = e.get("edge_id") or f"{e.get('src')}->{e.get('dst')}:{e.get('kind')}"
        inp.resources[rid] = {"resource_id": rid, "attrs": e,
                              "fact_ids": e.get("fact_ids", [])}
    return inp


def _classify_diff(attrs_before: dict, attrs_after: dict) -> tuple[str, list[str]]:
    """Semantic drift class from changed attribute keys (§102–104).

    Only keys present on BOTH sides are compared: a declared attr the
    provider simply doesn't echo is not evidence of drift — that's a
    shape difference, not a change. Keys only in `attrs_after` are
    provider-side additions and are likewise not drift."""
    changed = sorted(k for k in attrs_before if k in attrs_after
                     and attrs_before[k] != attrs_after[k])
    cats = set()
    for k in changed:
        for cat, names in _ATTR_TO_CATEGORY.items():
            if any(n in k for n in names):
                cats.add(cat)
    if cats:
        cls = _ATTR_CLASS_HINTS.get(min(cats), "config-drift")
    else:
        cls = "config-drift"
    return cls, changed


def reconcile(*, desired: CompareInput | None = None,
              planned: CompareInput | None = None,
              observed: CompareInput | None = None,
              runtime: CompareInput | None = None,
              accepted: list[dict[str, Any]] | None = None,
              at=None) -> dict[str, Any]:
    """N-way reconcile. Returns drift events + unresolved + alignment."""
    desired = desired or CompareInput("desired")
    planned = planned or CompareInput("planned")
    observed = observed or CompareInput("observed")
    runtime = runtime or CompareInput("runtime")
    accepted = accepted or []

    # §103 — temporal alignment: refuse to pretend snapshots are
    # simultaneous when they are not.
    stamps = {i.layer: i.timestamp for i in (desired, planned, observed)
              if i.timestamp}
    obs_stale = bool(observed.resources) and not observed.fresh
    obs_cov = observed.coverage
    obs_scope = ObservationScope.from_dict(observed.scope)

    events: list[DriftEvent] = []
    unresolved: list[dict[str, Any]] = []
    n = 0

    def _emit(rid: str, cls: str, before: dict, after: dict,
              facts: list[str] | None = None) -> DriftEvent:
        nonlocal n
        assert cls in DRIFT_CLASSES, cls
        n += 1
        ev = DriftEvent(
            drift_id=f"drift-{canonical_hash({'r': rid, 'c': cls})[:12]}",
            resource_id=rid, drift_class=cls,
            before=before, after=after, facts=facts or [],
            observed_at=observed.timestamp or now_iso())
        for a in accepted:
            if a.get("resource_id") in (rid, "*") and \
                    (a.get("drift_class") in (cls, "*", "")):
                ev.owner = "accepted"
                break
        events.append(ev)
        return ev

    def _grouped(layer_in: CompareInput):
        """Collapse multi-key entries to one canonical record set."""
        seen: dict[str, dict] = {}
        for res in layer_in.resources.values():
            seen.setdefault(res["resource_id"], res)
        return seen

    des = _grouped(desired)
    pln = _grouped(planned)
    obs = _grouped(observed)
    # matching needs the full multi-key index (uid/arn/kind:ns:name),
    # not just the collapsed resource_id map
    des_idx, pln_idx, obs_idx = (desired.resources, planned.resources,
                               observed.resources)

    # desired ↔ observed
    for rid, d in sorted(des.items()):
        target = {"resource_type": d.get("resource_type", ""),
                  "namespace": d.get("attrs", {}).get("namespace", ""),
                  "name": d.get("name") or d.get("resource_id", "")}
        match = next((obs_idx[k] for k in _keys_of(d)
                      if k in obs_idx), None)
        if match is None:
            if obs_cov in ("permission-limited", "unknown") or \
                    obs_cov == "" and not obs:
                unresolved.append({"resource_id": rid,
                                   "reason": f"coverage={obs_cov or 'none'}",
                                   "drift_class": "permission-unknown"
                                   if obs_cov == "permission-limited"
                                   else "unknown"})
                continue
            if obs_stale:
                _emit(rid, "stale-observation", d, {}, d.get("fact_ids"))
                continue
            if not obs_scope.covers(target)[0]:
                _emit(rid, "scope-mismatch", d, {}, d.get("fact_ids"))
                continue
            _emit(rid, "desired-missing-observed", d, {}, d.get("fact_ids"))
            continue
        if obs_stale:
            _emit(rid, "stale-observation", d, match, d.get("fact_ids"))
            continue
        cls, changed = _classify_diff(d.get("attrs", {}),
                                      match.get("attrs", {}))
        if changed:
            _emit(rid, cls, d, match, d.get("fact_ids"))
        else:
            _emit(rid, "converged", d, match, d.get("fact_ids"))

    # planned-not-applied: in plan, absent from observed (with same
    # coverage honesty gates as desired-missing-observed)
    for rid, p in sorted(pln.items()):
        if rid in des and _same_resource(des[rid], p):
            continue
        match = next((obs_idx[k] for k in _keys_of(p)
                      if k in obs_idx), None)
        if match is None and obs and obs_cov == "complete" \
                and not obs_stale:
            _emit(rid, "planned-not-applied", p, {}, p.get("fact_ids"))

    # observed-orphan: present in observed, absent from desired+planned
    for rid, o in sorted(obs.items()):
        if any(k in des_idx for k in _keys_of(o)) or \
                any(k in pln_idx for k in _keys_of(o)):
            continue
        _emit(rid, "observed-orphan", {}, o, o.get("fact_ids"))

    # runtime-undeclared: runtime edges with no desired/planned anchor
    for rid, r in sorted(_grouped(runtime).items()):
        if any(k in des_idx for k in _keys_of(r)) or \
                any(k in pln_idx for k in _keys_of(r)):
            continue
        _emit(rid, "runtime-undeclared", {}, r, r.get("fact_ids"))

    counts: dict[str, int] = {}
    accepted_n = 0
    for e in events:
        counts[e.drift_class] = counts.get(e.drift_class, 0) + 1
        if e.owner == "accepted":
            accepted_n += 1
    return {
        "drift": [e.to_dict() for e in events],
        "counts": counts, "accepted": accepted_n,
        "unresolved": unresolved,
        "alignment": {
            "timestamps": stamps,
            "comparable": bool(stamps) and not obs_stale,
            "observed_freshness": "fresh" if observed.fresh else "stale",
            "observed_coverage": obs_cov,
            "note": ("snapshots are not simultaneous — stale/"
                     "uncomparable classes applied where required"
                     if obs_stale else "")},
        "totals": {"drift_events": len(events),
                   "unresolved": len(unresolved)}}


def _same_resource(a: dict, b: dict) -> bool:
    return bool(_keys_of(a) & _keys_of(b))
