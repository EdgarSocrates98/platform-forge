"""Host parity — emit integration config per host. Same server, same core,
host-specific transport config only. Detach removes cleanly."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SERVER_CMD = ["python", "-m", "platformforge", "mcp", "serve"]


def integrate(host: str, root: str | Path) -> dict[str, Any]:
    root = Path(root)
    entry = {"command": SERVER_CMD[0],
             "args": SERVER_CMD[1:],
             "env": {}}
    if host == "claude":
        p = root / ".mcp.json"
        cfg = json.loads(p.read_text()) if p.exists() else {"mcpServers": {}}
        cfg.setdefault("mcpServers", {})["platformforge"] = entry
        p.write_text(json.dumps(cfg, indent=2) + "\n")
        return {"host": host, "wrote": str(p)}
    if host == "codex":
        p = root / ".codex" / "config.toml"
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a") as fh:
            fh.write('\n[mcp_servers.platformforge]\n'
                     f'command = "{SERVER_CMD[0]}"\n'
                     f'args = {json.dumps(SERVER_CMD[1:])}\n')
        return {"host": host, "wrote": str(p)}
    if host == "devin":
        p = root / ".devin" / "mcp_config.local.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        cfg = json.loads(p.read_text()) if p.exists() else {"mcpServers": {}}
        cfg.setdefault("mcpServers", {})["platformforge"] = entry
        p.write_text(json.dumps(cfg, indent=2) + "\n")
        return {"host": host, "wrote": str(p),
                "note": "local-only file — never commit secrets here"}
    if host == "copilot":
        p = root / ".vscode" / "mcp.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        cfg = json.loads(p.read_text()) if p.exists() else {"servers": {}}
        cfg.setdefault("servers", {})["platformforge"] = {
            "type": "stdio", "command": SERVER_CMD[0],
            "args": SERVER_CMD[1:]}
        p.write_text(json.dumps(cfg, indent=2) + "\n")
        return {"host": host, "wrote": str(p)}
    return {"host": "generic",
            "snippet": {"mcpServers": {"platformforge": entry}},
            "note": "merge into your host's MCP config"}


def detach(host: str, root: str | Path) -> dict[str, Any]:
    root = Path(root)
    targets = {"claude": root / ".mcp.json",
               "devin": root / ".devin" / "mcp_config.local.json",
               "copilot": root / ".vscode" / "mcp.json"}
    p = targets.get(host)
    if p is None:
        return {"host": host, "detached": False,
                "note": "generic host has nothing to remove"}
    if not p.exists():
        return {"host": host, "detached": False, "note": "not integrated"}
    cfg = json.loads(p.read_text())
    key = "mcpServers" if "mcpServers" in cfg else "servers"
    removed = cfg.get(key, {}).pop("platformforge", None)
    p.write_text(json.dumps(cfg, indent=2) + "\n")
    return {"host": host, "detached": removed is not None}
