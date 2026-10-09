from __future__ import annotations
import json
from pathlib import Path
from platformforge import __version__
from platformforge.workspace.models import WorkspaceManifest, WorkspaceMember

def _path(root: Path) -> Path:
    return root / ".platformforge" / "workspace.json"

def ensure_workspace(root: str | Path, profile: str = "agentic",
                     hosts: list[str] | None = None) -> WorkspaceManifest:
    root = Path(root).resolve()
    p = _path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.is_file():
        ws = WorkspaceManifest.from_dict(json.loads(p.read_text()))
        ws.profile, ws.hosts, ws.installed_version = profile, hosts or ws.hosts, __version__
    else:
        ws = WorkspaceManifest(str(root), profile, hosts or [], [],
                               "workspace-local", __version__)
    p.write_text(json.dumps(ws.to_dict(), indent=2, sort_keys=True) + "\n")
    return ws

def load_workspace(root: str | Path) -> WorkspaceManifest:
    p = _path(Path(root).resolve())
    if not p.is_file():
        raise FileNotFoundError("PF-WORKSPACE-MANIFEST-MISSING")
    return WorkspaceManifest.from_dict(json.loads(p.read_text()))

def add_repo(root: str | Path, repo: str | Path, name: str = "") -> WorkspaceManifest:
    root = Path(root).resolve()
    ws = ensure_workspace(root)
    rp = Path(repo).resolve()
    if rp != root and root not in rp.parents:
        # external members are explicit, but never silently inferred
        rel = str(rp)
    else:
        rel = str(rp.relative_to(root)) or "."
    name = name or rp.name
    if not any(x.name == name for x in ws.repos):
        ws.repos.append(WorkspaceMember(name, rel))
    _path(root).write_text(json.dumps(ws.to_dict(), indent=2, sort_keys=True) + "\n")
    return ws

def remove_repo(root: str | Path, name: str) -> WorkspaceManifest:
    root = Path(root).resolve()
    ws = load_workspace(root)
    ws.repos = [x for x in ws.repos if x.name != name]
    _path(root).write_text(json.dumps(ws.to_dict(), indent=2, sort_keys=True) + "\n")
    return ws

def doctor(root: str | Path) -> dict:
    root = Path(root).resolve()
    try:
        ws = load_workspace(root)
    except FileNotFoundError:
        return {"state": "failed", "refusal": "PF-WORKSPACE-MANIFEST-MISSING"}
    missing = []
    for m in ws.repos:
        p = Path(m.path)
        if not p.is_absolute():
            p = root / p
        if not p.exists():
            missing.append(m.name)
    return {"state": "healthy" if not missing else "warning",
            "workspace": ws.to_dict(), "missing_repos": missing}
