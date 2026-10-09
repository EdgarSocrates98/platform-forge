"""Workspace model — Platform Forge works globally-installed, inside a repo,
across multi-repo workspaces, in CI and in containers.

`workspace.yaml` at a root joins related repos (application / infra / gitops /
platform) into one analyzable system.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

PF_DIR = ".platformforge"
WORKSPACE_FILE = "workspace.yaml"


@dataclass
class WorkspaceMember:
    name: str
    path: str
    role: str = ""  # application | infra | gitops | platform
    attrs: dict[str, Any] = field(default_factory=dict)


@dataclass
class Workspace:
    root: Path
    members: list[WorkspaceMember] = field(default_factory=list)
    name: str = ""

    @property
    def pf_dir(self) -> Path:
        return self.root / PF_DIR

    @property
    def is_multi_repo(self) -> bool:
        return len(self.members) > 1

    def member_paths(self) -> list[Path]:
        if not self.members:
            return [self.root]
        return [(self.root / m.path).resolve() for m in self.members]


def find_root(start: str | Path) -> Path:
    """Walk up to the nearest .platformforge/ or workspace.yaml, else `start`."""
    p = Path(start).resolve()
    for cand in [p, *p.parents]:
        if (cand / PF_DIR).is_dir() or (cand / WORKSPACE_FILE).is_file():
            return cand
    return p


def init_workspace(root: str | Path, name: str = "") -> Path:
    root = Path(root).resolve()
    pf = root / PF_DIR
    for sub in ("store", "receipts", "cache", "sdd", "ledger"):
        (pf / sub).mkdir(parents=True, exist_ok=True)
    ws = root / WORKSPACE_FILE
    if not ws.exists():
        ws.write_text(
            yaml.safe_dump(
                {"schema": "platformforge/workspace/v1",
                 "name": name or root.name,
                 "members": [{"name": root.name, "path": ".", "role": "platform"}]},
                sort_keys=False,
            )
        )
    return pf


def load_workspace(start: str | Path) -> Workspace:
    root = find_root(start)
    ws_file = root / WORKSPACE_FILE
    members: list[WorkspaceMember] = []
    name = root.name
    if ws_file.is_file():
        doc = yaml.safe_load(ws_file.read_text()) or {}
        name = doc.get("name", name)
        for m in doc.get("members", []):
            members.append(WorkspaceMember(
                name=m.get("name", ""), path=m.get("path", "."),
                role=m.get("role", ""), attrs={k: v for k, v in m.items()
                                              if k not in ("name", "path", "role")},
            ))
    return Workspace(root=root, members=members, name=name)
