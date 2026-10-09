from __future__ import annotations
from dataclasses import asdict, dataclass, field
from typing import Any

SCHEMA = "platformforge/workspace-manifest/v1"

@dataclass
class WorkspaceMember:
    name: str
    path: str

@dataclass
class WorkspaceManifest:
    root: str
    profile: str = "agentic"
    hosts: list[str] = field(default_factory=list)
    repos: list[WorkspaceMember] = field(default_factory=list)
    state_mode: str = "workspace-local"
    installed_version: str = ""
    schema: str = SCHEMA

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["repos"] = [asdict(x) for x in self.repos]
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "WorkspaceManifest":
        return cls(root=d["root"], profile=d.get("profile", "agentic"),
                   hosts=list(d.get("hosts", [])),
                   repos=[WorkspaceMember(**x) for x in d.get("repos", [])],
                   state_mode=d.get("state_mode", "workspace-local"),
                   installed_version=d.get("installed_version", ""),
                   schema=d.get("schema", SCHEMA))
