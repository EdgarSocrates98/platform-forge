"""Cycle 3 — observation model. Canonical contracts for live evidence.

The load-bearing invariant: **OBSERVED ≠ COMPLETE**. Every observation
carries explicit scope + coverage + freshness so absence is only a
verdict when it was actually *seen to be absent* under a complete, fresh,
covering observation (ADR-0013/0014).

Runtime is not a provenance (cycle §4): `source_type=runtime` +
`tier=T0` on extracted facts keeps the distinction without inventing a
new provenance value.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

SCHEMA = "platformforge/observation/v1"
RECEIPT_SCHEMA = "platformforge/collector-receipt/v1"
CHANGE_EVENT_SCHEMA = "platformforge/change-event/v1"
DRIFT_EVENT_SCHEMA = "platformforge/drift-event/v1"

SOURCE_TYPES = ("observed", "runtime")
COVERAGE_STATUSES = ("complete", "partial", "sampled", "truncated",
                     "permission-limited", "unsupported", "unknown")
FRESHNESS_STATUSES = ("fresh", "aging", "stale", "expired", "unknown")
LIFECYCLES = ("present", "deleting", "deleted", "unknown")
BUDGET_OUTCOMES = ("complete", "reduced_scope", "sampled", "refused")

# §9 — default per-source TTLs (seconds); configurable per domain/source,
# never a hidden universal constant embedded in logic.
DEFAULT_FRESH_TTL: dict[str, int] = {
    "runtime": 120, "kubernetes": 300, "aws": 3600, "default": 900}

_OBS_ID_RE = re.compile(r"^obs-[0-9a-f]{16}$")


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def age_seconds(captured_at: str | None, at: datetime | None = None) -> float | None:
    ts = parse_ts(captured_at)
    if ts is None:
        return None
    return ((at or datetime.now(timezone.utc)) - ts).total_seconds()


def canonical_hash(obj: Any) -> str:
    return hashlib.sha256(json.dumps(
        obj, sort_keys=True, separators=(",", ":"), default=str
    ).encode()).hexdigest()


@dataclass
class ObservationScope:
    """§7 — WHAT WAS OBSERVED? Explicit, declarative, comparable."""
    provider: str = ""
    accounts: list[str] = field(default_factory=list)
    regions: list[str] = field(default_factory=list)
    services: list[str] = field(default_factory=list)
    resource_types: list[str] = field(default_factory=list)
    namespaces: list[str] = field(default_factory=list)
    clusters: list[str] = field(default_factory=list)
    selectors: dict[str, Any] = field(default_factory=dict)
    exclusions: list[str] = field(default_factory=list)

    def covers(self, target: dict[str, Any]) -> tuple[bool, str]:
        """Is `target` inside this scope? Conservative: an unset axis
        means 'all' only if the axis was declared unbounded; otherwise
        exclusion/omission wins (honest gaps)."""
        checks = []
        if self.accounts:
            checks.append((target.get("account") in self.accounts,
                           f"account {target.get('account')} not in scope"))
        if self.regions:
            checks.append((target.get("region") in self.regions,
                           f"region {target.get('region')} not in scope"))
        if self.namespaces:
            checks.append((target.get("namespace") in self.namespaces,
                           f"namespace {target.get('namespace')} not in scope"))
        if self.clusters:
            checks.append((target.get("cluster") in self.clusters,
                           f"cluster {target.get('cluster')} not in scope"))
        if self.resource_types:
            checks.append((target.get("resource_type") in self.resource_types,
                           f"type {target.get('resource_type')} not in scope"))
        excl = target.get("resource_id") or target.get("name") or ""
        if excl and excl in self.exclusions:
            checks.append((False, f"{excl} explicitly excluded"))
        for ok, why in checks:
            if not ok:
                return False, why
        return True, "in scope"

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v not in ([], {}, "")}

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> ObservationScope:
        return cls(**{k: v for k, v in (d or {}).items() if k in cls.__dataclass_fields__})


@dataclass
class Coverage:
    """§8 — coverage is per-resource-type, never one global claim."""
    status: str = "unknown"
    per_resource_type: dict[str, str] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)

    def __post_init__(self):
        if self.status not in COVERAGE_STATUSES:
            raise ValueError(f"invalid coverage status: {self.status}")
        for rt, st in self.per_resource_type.items():
            if st not in COVERAGE_STATUSES:
                raise ValueError(f"invalid coverage for {rt}: {st}")

    def for_type(self, resource_type: str) -> str:
        return self.per_resource_type.get(resource_type, self.status)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"status": self.status}
        if self.per_resource_type:
            d["per_resource_type"] = dict(sorted(self.per_resource_type.items()))
        if self.reasons:
            d["reasons"] = self.reasons
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> Coverage:
        d = d or {}
        return cls(status=d.get("status", "unknown"),
                   per_resource_type=dict(d.get("per_resource_type", {})),
                   reasons=list(d.get("reasons", [])))


@dataclass
class Freshness:
    """§9 — captured_at + fresh_until → status at a point in time."""
    captured_at: str = ""
    fresh_until: str = ""
    status: str = "unknown"

    def status_at(self, at: datetime | None = None,
                  ttl: int | None = None) -> str:
        at = at or datetime.now(timezone.utc)
        cap = parse_ts(self.captured_at)
        if cap is None:
            return "unknown"
        until = parse_ts(self.fresh_until)
        if until is None and ttl:
            from datetime import timedelta
            until = cap + timedelta(seconds=ttl)
        age = (at - cap).total_seconds()
        if until is None:
            return "unknown"
        if at > until:
            span = (until - cap).total_seconds() or 1.0
            return "expired" if age > span * 2 else "stale"
        return "fresh" if age < 0.6 * (until - cap).total_seconds() else "aging"

    def to_dict(self) -> dict[str, Any]:
        d = {"captured_at": self.captured_at, "status": self.status}
        if self.fresh_until:
            d["fresh_until"] = self.fresh_until
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> Freshness:
        d = d or {}
        return cls(captured_at=d.get("captured_at", ""),
                   fresh_until=d.get("fresh_until", ""),
                   status=d.get("status", "unknown"))


@dataclass
class ObservedObject:
    """One provider-observed object inside an envelope."""
    resource_id: str                    # provider-native (arn/uid/path)
    resource_type: str                  # normalized kind (k8s:Deployment…)
    attributes: dict[str, Any] = field(default_factory=dict)  # redacted!
    provider: str = ""
    account: str = ""
    region: str = ""
    cluster: str = ""
    namespace: str = ""
    name: str = ""
    uid: str = ""
    lifecycle: str = "present"          # present|deleting|deleted|unknown
    deletion_evidence: str = ""         # strong evidence type if deleted
    content_hash: str = ""              # canonical normalized fingerprint
    observed_at: str = ""
    artifact: str = ""                  # artifact://sha256/… for raw doc

    def __post_init__(self):
        if self.lifecycle not in LIFECYCLES:
            raise ValueError(f"invalid lifecycle: {self.lifecycle}")
        if self.lifecycle == "deleted" and not self.deletion_evidence:
            raise ValueError(
                "lifecycle=deleted requires deletion_evidence "
                "(ADR-0013: missing-from-snapshot is not proof)")

    def fingerprint(self) -> str:
        """§144 — canonical normalized hash for delta ingestion."""
        return self.content_hash or canonical_hash({
            "id": self.resource_id, "type": self.resource_type,
            "attrs": self.attributes})

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if not self.content_hash:
            d["content_hash"] = self.fingerprint()
        return {k: v for k, v in d.items() if v not in ("", {}, [])}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ObservedObject:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class CollectorReceipt:
    """§18 — every collection emits an auditable receipt."""
    collector: str
    collector_version: str
    provider: str
    started_at: str
    completed_at: str = ""
    scope: dict[str, Any] = field(default_factory=dict)
    api_calls: int = 0
    pages: int = 0
    objects: int = 0
    bytes: int = 0
    throttles: int = 0
    retries: int = 0
    cache_hits: int = 0
    errors: list[str] = field(default_factory=list)
    permission_denied: list[dict[str, Any]] = field(default_factory=list)
    unsupported: list[str] = field(default_factory=list)
    cursor: str = ""
    metadata_only: bool = True
    fallback: str = ""
    coverage: dict[str, Any] = field(default_factory=dict)
    freshness: dict[str, Any] = field(default_factory=dict)
    budget_outcome: str = "complete"
    duration_s: float = 0.0

    def __post_init__(self):
        if self.budget_outcome not in BUDGET_OUTCOMES:
            raise ValueError(f"invalid budget outcome: {self.budget_outcome}")

    def to_dict(self) -> dict[str, Any]:
        d = {"schema": RECEIPT_SCHEMA, **asdict(self)}
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CollectorReceipt:
        return cls(**{k: v for k, v in d.items()
                      if k in cls.__dataclass_fields__})


@dataclass
class ObservationEnvelope:
    """§6 — canonical live-observation artifact (observation/v1)."""
    observation_id: str
    collector: str
    collector_version: str
    provider: str
    source_type: str                          # observed | runtime
    captured_at: str
    completed_at: str = ""
    fresh_until: str = ""
    scope: dict[str, Any] = field(default_factory=dict)
    coverage: dict[str, Any] = field(default_factory=lambda: {"status": "unknown"})
    pagination: dict[str, Any] = field(default_factory=dict)
    permissions: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    objects: list[dict[str, Any]] = field(default_factory=list)
    bytes: int = 0
    hashes: dict[str, Any] = field(default_factory=dict)
    receipt: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.source_type not in SOURCE_TYPES:
            raise ValueError(f"invalid source_type: {self.source_type}")
        if not _OBS_ID_RE.match(self.observation_id):
            raise ValueError(f"invalid observation_id: {self.observation_id}")

    @classmethod
    def new(cls, collector: str, version: str, provider: str,
            source_type: str, scope: ObservationScope | dict | None = None,
            captured_at: str | None = None, **kw) -> ObservationEnvelope:
        sc = (scope.to_dict() if isinstance(scope, ObservationScope)
              else (scope or {}))
        obs_id = "obs-" + canonical_hash(
            {"collector": collector, "provider": provider,
             "captured_at": captured_at or "", "scope": sc})[:16]
        return cls(observation_id=obs_id, collector=collector,
                   collector_version=version, provider=provider,
                   source_type=source_type,
                   captured_at=captured_at or now_iso(), scope=sc, **kw)

    def coverage_status(self, resource_type: str = "") -> str:
        cov = Coverage.from_dict(self.coverage)
        return cov.for_type(resource_type) if resource_type else cov.status

    def freshness_status_at(self, at: datetime | None = None) -> str:
        f = Freshness.from_dict({"captured_at": self.captured_at,
                                 "fresh_until": self.fresh_until})
        return f.status_at(at, ttl=DEFAULT_FRESH_TTL.get(
            self.provider, DEFAULT_FRESH_TTL["default"]))

    def can_conclude_absent(self, target: dict[str, Any],
                            at: datetime | None = None) -> tuple[bool, str]:
        """§10 — absence is only provable when scope covers the target
        AND coverage is complete for its type AND the snapshot is fresh.
        Everything else → unresolved."""
        in_scope, why = ObservationScope.from_dict(self.scope).covers(target)
        if not in_scope:
            return False, f"scope does not cover target: {why}"
        cov = self.coverage_status(target.get("resource_type", ""))
        if cov != "complete":
            return False, f"coverage={cov} — absence unresolved"
        fs = self.freshness_status_at(at)
        if fs != "fresh":
            return False, f"freshness={fs} — absence unresolved"
        return True, "absence provable (scope+complete+fresh)"

    def signature(self) -> str:
        return self.hashes.get("envelope") or canonical_hash(
            self.to_dict(include_hashes=False))

    def to_dict(self, include_hashes: bool = True) -> dict[str, Any]:
        d = {"schema": SCHEMA, "observation_id": self.observation_id,
             "collector": self.collector,
             "collector_version": self.collector_version,
             "provider": self.provider, "source_type": self.source_type,
             "captured_at": self.captured_at, "scope": self.scope,
             "coverage": self.coverage, "objects": self.objects}
        for k in ("completed_at", "fresh_until", "pagination",
                  "permissions", "bytes", "receipt"):
            v = getattr(self, k)
            if v not in ("", {}, [], 0):
                d[k] = v
        if self.errors:
            d["errors"] = self.errors
        if include_hashes:
            h = dict(self.hashes)
            h.setdefault("envelope", canonical_hash(
                {k: v for k, v in d.items() if k != "hashes"}))
            d["hashes"] = h
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ObservationEnvelope:
        return cls(**{k: v for k, v in d.items()
                      if k in cls.__dataclass_fields__})


@dataclass
class ChangeEvent:
    """§78 — provider-observed change evidence (CloudTrail et al., T1)."""
    event_id: str
    timestamp: str
    source: str                              # cloudtrail | k8s-event | …
    action: str
    actor: str = ""
    resource_ids: list[str] = field(default_factory=list)
    account: str = ""
    region: str = ""
    request: dict[str, Any] = field(default_factory=dict)   # redacted!
    result: str = ""                                        # success|error
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"schema": CHANGE_EVENT_SCHEMA,
                **{k: v for k, v in asdict(self).items() if v not in ("", {}, [])}}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ChangeEvent:
        return cls(**{k: v for k, v in d.items()
                      if k in cls.__dataclass_fields__})


@dataclass
class DriftEvent:
    """§113 — a classified change between two observations."""
    drift_id: str
    resource_id: str
    drift_class: str                         # §102 set
    before: dict[str, Any] = field(default_factory=dict)
    after: dict[str, Any] = field(default_factory=dict)
    facts: list[str] = field(default_factory=list)
    change_event: str = ""                   # event_id if correlated
    risk: str = ""
    owner: str = ""
    observed_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"schema": DRIFT_EVENT_SCHEMA,
                **{k: v for k, v in asdict(self).items() if v not in ("", {}, [])}}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> DriftEvent:
        return cls(**{k: v for k, v in d.items()
                      if k in cls.__dataclass_fields__})


# §102 — normative drift classes (closed set; validated, not free-text)
DRIFT_CLASSES = (
    "converged", "planned-not-applied", "observed-out-of-band",
    "desired-missing-observed", "observed-orphan", "config-drift",
    "identity-drift", "policy-drift", "security-drift", "network-drift",
    "version-drift", "runtime-undeclared", "stale-observation",
    "permission-unknown", "scope-mismatch", "uncomparable", "unknown")

# §125 — declared vs runtime behavior classes
BEHAVIOR_CLASSES = ("declared-and-observed", "observed-undeclared",
                    "declared-not-seen-in-window", "unknown")
