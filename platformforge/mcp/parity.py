"""Host parity — emit integration config per host. Same server, same core,
host-specific transport config only. Detach removes cleanly.

The MCP command is the installed console script ``platformforge-mcp`` —
never a bare ``python -m`` (a ``python`` binary is not guaranteed on the
consumer's PATH, and ``python -m platformforge`` has no ``mcp serve``
subcommand). JSON hosts get a managed key inside the shared config file
(tracked under ``_forge_managed``); codex gets an idempotent TOML table.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from platformforge import _installkit as kit

SERVER_CMD = ["platformforge-mcp"]
SERVER_NAME = "platformforge"
_TAG = "platform-forge"
_CODEX_TABLE = f"mcp_servers.{SERVER_NAME}"


def _entry() -> dict[str, Any]:
    return {"command": SERVER_CMD[0], "args": SERVER_CMD[1:], "env": {}}


def _load_shared(path: Path, host: str) -> dict[str, Any] | None:
    """Load an existing JSON config; a non-JSON file is a named refusal —
    we never overwrite what we cannot parse."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _write_json(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    kit._atomic_write(path, kit._json_bytes(doc))


def _strip_toml_table(text: str, table: str) -> str:
    """Remove a ``[table]`` section (header + body until the next header)
    from TOML text — dedupe before upsert, full removal on detach."""
    header = f"[{table}]"
    out: list[str] = []
    skipping = False
    for ln in text.splitlines(keepends=True):
        stripped = ln.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            skipping = stripped == header or stripped.startswith(header + ".")
            if skipping:
                continue
            out.append(ln)
            continue
        if not skipping:
            out.append(ln)
    return "".join(out)


def _codex_block() -> str:
    args = json.dumps(SERVER_CMD[1:])
    return (f"[{_CODEX_TABLE}]\n"
            f'command = "{SERVER_CMD[0]}"\n'
            f"args = {args}\n")


def integrate(host: str, root: str | Path) -> dict[str, Any]:
    root = Path(root)
    if host == "claude":
        p = root / ".mcp.json"
        cfg = _load_shared(p, host)
        if cfg is None:
            return {"host": host, "refusal": "PF-MCP-CONFIG-INVALID",
                    "detail": f"{p} exists but is not a JSON object — "
                              "fix or remove it, then re-run"}
        _write_json(p, kit.mcp_set(cfg, SERVER_NAME, _entry(), _TAG))
        return {"host": host, "wrote": str(p)}
    if host == "codex":
        p = root / ".codex" / "config.toml"
        p.parent.mkdir(parents=True, exist_ok=True)
        old = p.read_text(encoding="utf-8") if p.exists() else ""
        text = _strip_toml_table(old, _CODEX_TABLE)
        if text and not text.endswith("\n"):
            text += "\n"
        text += ("\n" if text.strip() else "") + _codex_block()
        kit._atomic_write(p, text.encode("utf-8"))
        return {"host": host, "wrote": str(p)}
    if host == "devin":
        p = root / ".devin" / "mcp_config.local.json"
        cfg = _load_shared(p, host)
        if cfg is None:
            return {"host": host, "refusal": "PF-MCP-CONFIG-INVALID",
                    "detail": f"{p} exists but is not a JSON object — "
                              "fix or remove it, then re-run"}
        _write_json(p, kit.mcp_set(cfg, SERVER_NAME, _entry(), _TAG))
        return {"host": host, "wrote": str(p),
                "note": "local-only file — never commit secrets here"}
    if host == "copilot":
        p = root / ".vscode" / "mcp.json"
        cfg = _load_shared(p, host)
        if cfg is None:
            return {"host": host, "refusal": "PF-MCP-CONFIG-INVALID",
                    "detail": f"{p} exists but is not a JSON object — "
                              "fix or remove it, then re-run"}
        cfg.setdefault("servers", {})[SERVER_NAME] = {
            "type": "stdio", "command": SERVER_CMD[0],
            "args": SERVER_CMD[1:]}
        _write_json(p, cfg)
        return {"host": host, "wrote": str(p)}
    return {"host": "generic",
            "snippet": {"mcpServers": {SERVER_NAME: _entry()}},
            "note": "merge into your host's MCP config"}


def detach(host: str, root: str | Path) -> dict[str, Any]:
    root = Path(root)
    if host == "codex":
        p = root / ".codex" / "config.toml"
        if not p.exists():
            return {"host": host, "detached": False, "note": "not integrated"}
        old = p.read_text(encoding="utf-8")
        new = _strip_toml_table(old, _CODEX_TABLE)
        if new == old:
            return {"host": host, "detached": False, "note": "not integrated"}
        kit._atomic_write(p, new.encode("utf-8"))
        return {"host": host, "detached": True}
    targets = {"claude": (root / ".mcp.json", "mcpServers"),
               "devin": (root / ".devin" / "mcp_config.local.json",
                         "mcpServers"),
               "copilot": (root / ".vscode" / "mcp.json", "servers")}
    found = targets.get(host)
    if found is None:
        return {"host": host, "detached": False,
                "note": "generic host has nothing to remove"}
    p, key = found
    if not p.exists():
        return {"host": host, "detached": False, "note": "not integrated"}
    cfg = _load_shared(p, host)
    if cfg is None:
        return {"host": host, "detached": False,
                "refusal": "PF-MCP-CONFIG-INVALID",
                "detail": f"{p} exists but is not a JSON object"}
    if key == "mcpServers":
        new = kit.mcp_unset(cfg, SERVER_NAME, _TAG)
    else:
        servers = dict(cfg.get(key) or {})
        removed = servers.pop(SERVER_NAME, None)
        if servers:
            cfg[key] = servers
        else:
            cfg.pop(key, None)
        new = cfg
        if removed is None:
            return {"host": host, "detached": False}
    removed = (p.read_text(encoding="utf-8") !=
               (kit._json_bytes(new).decode("utf-8")))
    if new:
        _write_json(p, new)
    else:
        p.unlink()
    return {"host": host, "detached": removed}
