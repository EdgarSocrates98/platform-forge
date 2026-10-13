"""Versioned contracts for portable distribution."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

DIST_SCHEMA = "platformforge/distribution-manifest/v1"
INSTALL_PLAN_SCHEMA = "platformforge/install-plan/v1"
INSTALL_RECEIPT_SCHEMA = "platformforge/install-receipt/v1"

@dataclass(frozen=True)
class ManagedAsset:
    path: str
    sha256: str
    owner: str = "platformforge"
    kind: str = "asset"

@dataclass
class DistributionManifest:
    distribution_id: str
    platformforge_version: str
    source_sha: str = ""
    profile: str = "agentic"
    hosts: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    assets: list[ManagedAsset] = field(default_factory=list)
    offline: bool = True
    schema: str = DIST_SCHEMA

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["assets"] = [asdict(x) for x in self.assets]
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> DistributionManifest:
        return cls(
            distribution_id=d["distribution_id"],
            platformforge_version=d["platformforge_version"],
            source_sha=d.get("source_sha", ""),
            profile=d.get("profile", "agentic"),
            hosts=list(d.get("hosts", [])),
            capabilities=list(d.get("capabilities", [])),
            assets=[ManagedAsset(**x) for x in d.get("assets", [])],
            offline=bool(d.get("offline", True)),
            schema=d.get("schema", DIST_SCHEMA),
        )

@dataclass
class InstallPlan:
    target: str
    profile: str
    hosts: list[str]
    creates: list[str] = field(default_factory=list)
    identical: list[str] = field(default_factory=list)
    managed_updates: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    network_required: bool = False
    schema: str = INSTALL_PLAN_SCHEMA

    @property
    def safe(self) -> bool:
        return not self.conflicts

    def to_dict(self) -> dict[str, Any]:
        return asdict(self) | {"safe": self.safe}

@dataclass
class InstallReceipt:
    distribution_id: str
    platformforge_version: str
    source_sha: str
    target: str
    profile: str
    hosts: list[str]
    files: dict[str, str]
    schema: str = INSTALL_RECEIPT_SCHEMA

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
