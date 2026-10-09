"""Cycle 5 Phase A — fleet contracts (§13–16, §23–24, §176).

Invariants baked into the schema:
- members identified by canonical IDs, never name alone (§15);
- a FleetSnapshot stores *references/hashes* to member snapshots, not
  duplicated resources (§24);
- every member observation carries coverage + freshness — fleet
  conclusions inherit the worst member coverage (§374);
- data classification is mandatory on exports (§176).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from platformforge.live.models import canonical_hash, now_iso

SCHEMA = "platformforge/fleet/v1"
SNAPSHOT_SCHEMA = "platformforge/fleet-snapshot/v1"

MEMBER_KINDS = ("cluster", "cloud_account", "subscription", "project",
                "repository", "service", "team", "environment", "region")
CLASSIFICATIONS = ("public", "internal", "sensitive", "restricted")
OBS_STATUSES = ("observed", "permission-limited", "unavailable",
                "stale", "not-configured")


@dataclass
class FleetMember:
    """§15 — canonical identity: kind + canonical_id (+ human name)."""
    kind: str
    canonical_id: str            # e.g. k8s:prod-1, aws:123456789012
    name: str = ""
    environment: str = ""
    team: str = ""
    region: str = ""
    labels: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MemberObservation:
    """Per-member observation envelope — coverage is first-class."""
    member_id: str
    status: str = "observed"           # OBS_STATUSES
    coverage: float = 1.0              # 0..1 fraction of intended scope
    freshness: str = "fresh"
    observed_at: str = ""
    snapshot_ref: str = ""             # hash/ref — not the payload
    fact_count: int = 0
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Fleet:
    """§14 — fleet schema."""
    fleet_id: str
    organization: str = ""
    environments: list[str] = field(default_factory=list)
    members: list[FleetMember] = field(default_factory=list)
    labels: dict[str, str] = field(default_factory=dict)
    ownership: dict[str, str] = field(default_factory=dict)
    policies: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"schema": SCHEMA, "fleet_id": self.fleet_id,
                "organization": self.organization,
                "environments": self.environments,
                "members": {"clusters": [m.to_dict() for m in self.members
                                         if m.kind == "cluster"],
                            "cloud_accounts": [m.to_dict() for m in self.members
                                               if m.kind == "cloud_account"],
                            "repositories": [m.to_dict() for m in self.members
                                             if m.kind == "repository"],
                            "services": [m.to_dict() for m in self.members
                                         if m.kind == "service"],
                            "teams": [m.to_dict() for m in self.members
                                      if m.kind == "team"],
                            "other": [m.to_dict() for m in self.members
                                      if m.kind not in
                                      ("cluster", "cloud_account",
                                       "repository", "service", "team")]},
                "labels": self.labels, "ownership": self.ownership,
                "policies": self.policies}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Fleet:
        members = []
        raw = d.get("members", {})
        groups = raw.values() if isinstance(raw, dict) else [raw]
        for group in groups:
            for m in group:
                members.append(FleetMember(**{
                    k: v for k, v in m.items()
                    if k in FleetMember.__dataclass_fields__}))
        return cls(fleet_id=d["fleet_id"],
                   organization=d.get("organization", ""),
                   environments=d.get("environments", []),
                   members=members, labels=d.get("labels", {}),
                   ownership=d.get("ownership", {}),
                   policies=d.get("policies", []))


@dataclass
class FleetSnapshot:
    """§23–24 — references member snapshots by hash; coverage is the
    *minimum* of member coverages (property test §296)."""
    fleet_id: str
    captured_at: str = ""
    member_observations: list[MemberObservation] = field(
        default_factory=list)
    graph_ref: str = ""                # hash of merged fleet graph
    fact_refs: list[str] = field(default_factory=list)

    @property
    def coverage(self) -> float:
        obs = self.member_observations
        if not obs:
            return 0.0
        return min(o.coverage for o in obs)

    @property
    def coverage_ratio(self) -> str:
        obs = self.member_observations
        ok = sum(1 for o in obs if o.status == "observed")
        return f"{ok}/{len(obs)}"

    def to_dict(self) -> dict[str, Any]:
        return {"schema": SNAPSHOT_SCHEMA, "fleet_id": self.fleet_id,
                "captured_at": self.captured_at or now_iso(),
                "coverage": {"ratio": self.coverage_ratio,
                             "min_member": self.coverage},
                "member_observations": [o.to_dict()
                                        for o in self.member_observations],
                "graph_ref": self.graph_ref, "fact_refs": self.fact_refs,
                "hash": "sha256:" + canonical_hash(
                    [o.to_dict() for o in self.member_observations]
                    + self.fact_refs)}


def member_key(kind: str, canonical_id: str) -> str:
    """§15/§300 — names may collide across teams/envs; IDs never do."""
    return f"{kind}:{canonical_id}"


def classify(value: str | None, default: str = "internal") -> str:
    """§176 — data classification with safe default (never leaks as
    public by accident)."""
    return value if value in CLASSIFICATIONS else default
