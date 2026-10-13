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
    Coverage,
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
    coverage: str = "unknown"                    # observed only (global)
    coverage_detail: dict[str, Any] = field(default_factory=dict)
    scope: dict[str, Any] = field(default_factory=dict)
    fresh: bool = True


def _keys_of(res: dict[str, Any]) -> set[str]:
    """Candidate match keys — strong first, weak triple as fallback.

    Normalization (audit X1c): a `resource_id` carrying a `#uid` suffix
    (k8s collector shape `k8s://cluster/ns/Kind/name#uid`) yields both
    the full id and the uid-stripped base so desired facts written as
    `k8s://lab/prod/Deployment/api` match the observed object. The uid
    fragment is additionally indexed as `uid:<frag>`. Kind triples are
    emitted for both the full resource_type (`k8s:apps/Deployment`) and
    its short form (`Deployment`) so facts that only know the short
    kind still join."""
    keys = set()
    attrs = res.get("attrs") or res.get("attributes") or {}
    for k in ("arn", "uid", "resource_id", "canonical_id",
              "terraform_address"):
        v = attrs.get(k) or res.get(k)
        if v:
            keys.add(str(v))
    rid = res.get("resource_id") or res.get("location") or ""
    if rid:
        rid = str(rid)
        keys.add(rid)
        if "#" in rid:
            base, _, frag = rid.rpartition("#")
            if base:
                keys.add(base)
            if frag:
                keys.add(f"uid:{frag}")
    if res.get("uid"):
        keys.add(f"uid:{res['uid']}")
    kind = res.get("resource_type") or res.get("kind", "")
    ns = res.get("namespace", "") or attrs.get("namespace", "")
    name = res.get("name", "") or attrs.get("name", "")
    if kind and name:
        keys.add(f"{kind}:{ns}:{name}")
        short = str(kind).rsplit("/", 1)[-1].rsplit(":", 1)[-1]
        if short != kind:
            keys.add(f"{short}:{ns}:{name}")
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
                       coverage_detail=dict(env.coverage or {}),
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
              resolve_identities: bool = True,
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
    cov_detail = Coverage.from_dict(observed.coverage_detail or
                                    {"status": obs_cov})
    obs_scope = ObservationScope.from_dict(observed.scope)

    # Identity resolution (§42–§49): union strong ids across layers so a
    # desired terraform_address joins the observed ARN it produced, and
    # SA↔role contradictions surface as identity-drift — never silently.
    links: list[dict[str, Any]] = []
    ident_summary: dict[str, Any] = {}
    alias_map: dict[str, set[str]] = {}
    if resolve_identities and (observed.resources or desired.resources
                               or planned.resources):
        from platformforge.live.identity import IdentityResolver
        res = IdentityResolver()
        seen_objs: set[int] = set()
        for inp in (observed, desired, planned):
            for r in inp.resources.values():
                if id(r) in seen_objs:
                    continue
                seen_objs.add(id(r))
                res.ingest_object(dict(r, attributes=r.get("attrs", {})))
        resolved = res.resolve()
        links = resolved["links"]
        ident_summary = {"counts": resolved["counts"],
                         "weak_candidates": resolved["weak_candidates"],
                         "conflicts": resolved["conflicts"]}
        # every value an identity groups together becomes a match key —
        # terraform_address ↔ arn ↔ resource_id ↔ uid ↔ aliases
        for ident in resolved["identities"]:
            vals = ({str(v) for v in ident.get("provider_ids", {}).values()}
                    | {str(v) for v in ident.get("graph_nodes", [])}
                    | {str(v) for v in ident.get("aliases", [])}
                    | {str(ident.get("canonical_id", ""))})
            vals.discard("")
            for v in vals:
                alias_map.setdefault(v, set()).update(vals - {v})
        for l in links:
            a, b = str(l.get("a", "")), str(l.get("b", ""))
            if a and b:
                alias_map.setdefault(a, set()).add(b)
                alias_map.setdefault(b, set()).add(a)

    def _match_keys(res: dict[str, Any]) -> set[str]:
        """_keys_of + resolved-identity alias expansion."""
        keys = _keys_of(res)
        if not alias_map:
            return keys
        out = set(keys)
        for k in keys:
            out.update(alias_map.get(k, ()))
        return out

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

    # identity conflicts surface as drift events, never silently merged
    for c in (ident_summary.get("conflicts") or []):
        _emit(c.get("resource", "unknown"), "identity-drift",
              dict(c.get("claim_a", {})), dict(c.get("claim_b", [])))

    # desired ↔ observed — per-type coverage gates absence verdicts
    for rid, d in sorted(des.items()):
        target = {"resource_type": d.get("resource_type", ""),
                  "namespace": d.get("attrs", {}).get("namespace", ""),
                  "name": d.get("name") or d.get("resource_id", "")}
        cov_t = cov_detail.for_type(
            d.get("resource_type", "")) or obs_cov
        match = next((obs_idx[k] for k in _match_keys(d)
                      if k in obs_idx), None)
        if match is None:
            if obs_cov == "" and not obs:
                unresolved.append({"resource_id": rid,
                                   "reason": "coverage=none",
                                   "drift_class": "unknown"})
                continue
            if cov_t != "complete":
                unresolved.append(
                    {"resource_id": rid,
                     "reason": f"coverage[{d.get('resource_type') or '?'}]"
                               f"={cov_t}",
                     "drift_class": "permission-unknown"
                     if cov_t in ("permission-limited", "unsupported")
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

    # planned-not-applied: in plan, absent from observed — gated on
    # per-type coverage: absence is unprovable where the type was not
    # fully collected (§8/§10)
    for rid, p in sorted(pln.items()):
        if rid in des and _same_resource(des[rid], p):
            continue
        match = next((obs_idx[k] for k in _match_keys(p)
                      if k in obs_idx), None)
        if match is None and obs and not obs_stale and \
                cov_detail.for_type(
                    p.get("resource_type", "")) == "complete":
            _emit(rid, "planned-not-applied", p, {}, p.get("fact_ids"))

    # observed-orphan: present in observed, absent from desired+planned
    for rid, o in sorted(obs.items()):
        if any(k in des_idx for k in _match_keys(o)) or \
                any(k in pln_idx for k in _match_keys(o)):
            continue
        _emit(rid, "observed-orphan", {}, o, o.get("fact_ids"))

    # runtime-undeclared: runtime edges with no desired/planned anchor
    for rid, r in sorted(_grouped(runtime).items()):
        if any(k in des_idx for k in _match_keys(r)) or \
                any(k in pln_idx for k in _match_keys(r)):
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
        "identities": ident_summary,
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
