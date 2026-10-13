"""Identity resolution (cycle §42–§49).

A ResourceIdentity is a UNION over strong identifiers — ARN, k8s UID,
immutable provider id. Weak names (name+kind+namespace) never merge
identities on their own; they produce `weak_candidates` for review.

Every link carries {confidence, provenance, fact_ids, reason}.
Contradictions are surfaced as IdentityConflict — never silently
resolved (e.g. SA annotation → role A while EKS Pod Identity → role B).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

STRONG_ID_KINDS = ("arn", "uid", "canonical_id", "provider_id",
                   "tf_address", "config_id")
LINK_CONFIDENCE = {"exact-arn": 1.0, "exact-uid": 1.0,
                   "tf-address": 0.95, "pod-identity": 0.95,
                   "irsa-annotation": 0.9, "config-record": 0.9,
                   "name-only": 0.4}

IRSA_ANNOTATION = "eks.amazonaws.com/role-arn"


@dataclass
class IdentityLink:
    a: str
    b: str
    reason: str                       # e.g. exact-arn, pod-identity
    confidence: float
    provenance: str = "observed"
    fact_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"a": self.a, "b": self.b, "reason": self.reason,
                "confidence": self.confidence,
                "provenance": self.provenance,
                "fact_ids": sorted(self.fact_ids)}


@dataclass
class IdentityConflict:
    kind: str                         # e.g. sa-role-conflict
    resource: str
    claim_a: dict[str, Any]
    claim_b: dict[str, Any]
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "resource": self.resource,
                "claim_a": self.claim_a, "claim_b": self.claim_b,
                "detail": self.detail}


@dataclass
class ResourceIdentity:
    canonical_id: str
    provider_ids: dict[str, str] = field(default_factory=dict)
    graph_nodes: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"canonical_id": self.canonical_id,
                "provider_ids": dict(sorted(self.provider_ids.items())),
                "graph_nodes": sorted(self.graph_nodes),
                "aliases": sorted(self.aliases),
                "evidence": self.evidence}


class _UnionFind:
    def __init__(self):
        self.p: dict[str, str] = {}

    def find(self, x: str) -> str:
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


def strong_ids_of(obj: dict[str, Any]) -> dict[str, str]:
    """Extract strong identifiers from an observed object or fact."""
    ids: dict[str, str] = {}
    attrs = obj.get("attributes") or obj.get("attrs") or {}
    if attrs.get("arn"):
        ids["arn"] = attrs["arn"]
    rid = obj.get("resource_id", "")
    if rid.startswith("arn:"):
        ids["arn"] = rid
    if obj.get("uid"):
        ids["uid"] = obj["uid"]
    if rid.startswith(("k8s://", "aws://")) and "#" in rid:
        ids["uid"] = rid.rsplit("#", 1)[-1]
    if rid:
        ids["canonical_id"] = rid
    if attrs.get("terraform_address") or obj.get("terraform_address"):
        ids["tf_address"] = attrs.get("terraform_address") or \
            obj.get("terraform_address")
    return ids


def sa_role_claims(objects: list[dict[str, Any]]) -> list[IdentityConflict]:
    """§47 — ServiceAccount role resolution conflict detector.

    IRSA annotation (k8s object) vs EKS Pod Identity association (aws
    object): different role → explicit conflict.
    """
    sa_annotated: dict[tuple[str, str], dict[str, Any]] = {}
    pod_id: dict[tuple[str, str], dict[str, Any]] = {}
    for o in objects:
        a = o.get("attributes", {})
        rt = o.get("resource_type", "")
        if rt == "k8s:ServiceAccount":
            role = (a.get("annotations") or {}).get(IRSA_ANNOTATION)
            if role:
                sa_annotated[(o.get("cluster", ""), o.get("namespace", ""),
                              o.get("name", ""))] = \
                    {"role_arn": role, "source": "irsa-annotation",
                     "object": o.get("resource_id", "")}
        elif rt == "aws:eks/pod_identity_association":
            pod_id[(o.get("cluster", ""), a.get("namespace", ""),
                    a.get("service_account", ""))] = \
                {"role_arn": a.get("role_arn", ""),
                 "source": "pod-identity",
                 "object": o.get("resource_id", "")}
    conflicts = []
    for key, sa in sorted(sa_annotated.items()):
        pi = pod_id.get(key)
        if pi and pi["role_arn"] != sa["role_arn"]:
            conflicts.append(IdentityConflict(
                kind="sa-role-conflict", resource=key[2],
                claim_a=sa, claim_b=pi,
                detail=f"namespace={key[1]} cluster={key[0]}: IRSA "
                       f"annotation={sa['role_arn']} vs "
                       f"PodIdentity={pi['role_arn']}"))
    return conflicts


class IdentityResolver:
    """Ingests objects/facts, unions strong ids, emits identities +
    links + conflicts + unresolved weak candidates."""

    def __init__(self):
        self._uf = _UnionFind()
        self._records: dict[str, dict[str, Any]] = {}
        self._links: list[IdentityLink] = []
        self._weak: dict[str, dict[str, Any]] = {}
        self._conflicts: list[IdentityConflict] = []
        self._objects: list[dict[str, Any]] = []

    def ingest_object(self, obj: dict[str, Any]) -> None:
        self._objects.append(obj)
        ids = strong_ids_of(obj)
        rid = obj.get("resource_id", "")
        anchors = [f"{k}:{v}" for k, v in ids.items() if v]
        if not anchors:
            # weak-only shape: record for review, never auto-merge
            key = (f"weak:{obj.get('resource_type')}:"
                   f"{obj.get('namespace')}:{obj.get('name')}")
            self._weak.setdefault(key, obj)
            return
        if not rid:
            return
        self._records[rid] = obj
        for anchor in anchors[1:]:
            self._uf.union(anchors[0], anchor)
        self._uf.union(f"rid:{rid}", anchors[0])
        for kind, val in ids.items():
            self._records.setdefault(f"{kind}:{val}", {})

    def ingest_fact(self, fact: dict[str, Any]) -> None:
        attrs = fact.get("attrs", {}) or {}
        pseudo = {"resource_id": attrs.get("arn") or fact.get("location", ""),
                  "resource_type": fact.get("kind", ""),
                  "attributes": attrs}
        ids = strong_ids_of(pseudo)
        if ids:
            self.ingest_object({**pseudo, "resource_id":
                                pseudo["resource_id"] or
                                f"fact:{fact.get('fact_id','?')}",
                                "_fact": fact.get("fact_id", "")})

    def ingest_terraform(self, tf_address: str, arn_or_id: str,
                         fact_id: str = "") -> None:
        """§45 — terraform address ↔ provider id link (T3 declared ↔
        T1 observed)."""
        if not arn_or_id:
            return
        self._uf.union(f"tf_address:{tf_address}",
                       (f"arn:{arn_or_id}" if arn_or_id.startswith("arn:")
                        else f"canonical_id:{arn_or_id}"))
        self._links.append(IdentityLink(
            a=tf_address, b=arn_or_id, reason="tf-address",
            confidence=LINK_CONFIDENCE["tf-address"],
            provenance="declared",
            fact_ids=[fact_id] if fact_id else []))

    def ingest_pod_identity(self, *, cluster: str, namespace: str,
                            service_account: str, role_arn: str,
                            sa_uid: str = "",
                            fact_id: str = "") -> None:
        """§46 — EKS Pod Identity / IRSA: SA ↔ IAM role link."""
        sa_key = f"k8s-sa:{cluster}/{namespace}/{service_account}"
        self._uf.union(sa_key, f"arn:{role_arn}")
        self._links.append(IdentityLink(
            a=f"{namespace}/{service_account}", b=role_arn,
            reason="pod-identity",
            confidence=LINK_CONFIDENCE["pod-identity"],
            fact_ids=[fact_id] if fact_id else []))
        if sa_uid:
            self._uf.union(sa_key, f"uid:{sa_uid}")

    def resolve(self) -> dict[str, Any]:
        self._conflicts = sa_role_claims(self._objects)
        groups: dict[str, dict[str, Any]] = {}
        for key in self._uf.p:
            root = self._uf.find(key)
            g = groups.setdefault(root, {"ids": {}, "rids": set(),
                                         "facts": set()})
            kind, _, val = key.partition(":")
            if kind == "rid":
                g["rids"].add(val)
            elif kind == "k8s-sa":
                g["ids"]["service_account"] = val
            else:
                g["ids"][kind] = val
        identities: list[ResourceIdentity] = []
        for g in groups.values():
            ids = g["ids"]
            canonical = (ids.get("arn") or ids.get("uid")
                         or (min(g["rids"]) if g["rids"]
                             else next(iter(ids.values()), "")))
            ident = ResourceIdentity(
                canonical_id=canonical,
                provider_ids={k: v for k, v in ids.items()
                              if k in STRONG_ID_KINDS or k == "service_account"},
                graph_nodes=sorted(g["rids"]),
                aliases=sorted(set(ids.values()) - {canonical}))
            identities.append(ident)
        return {
            "identities": [i.to_dict() for i in sorted(
                identities, key=lambda i: i.canonical_id)],
            "links": [l.to_dict() for l in self._links],
            "conflicts": [c.to_dict() for c in self._conflicts],
            "weak_candidates": sorted(self._weak),
            "counts": {"identities": len(identities),
                       "links": len(self._links),
                       "conflicts": len(self._conflicts),
                       "weak": len(self._weak)}}
